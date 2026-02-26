from __future__ import annotations

import json
import logging
from http import HTTPStatus
from logging import Logger
from typing import IO, Annotated

import httpx
from fastapi import Depends, Request

# `HTTPRequester` below is legacy/request-scoped and depends on modules that are
# not always present in the slim PB runtime. Keep shared transport (`HTTPClient`,
# `post_json`) always available and gate the legacy layer behind optional imports.
_LEGACY_REQUESTER_AVAILABLE = True
_LEGACY_REQUESTER_IMPORT_ERROR: Exception | None = None

try:
    from common.logger import Logging
    from constant.enums import ResponseCodeEnum
    from core.access import AccessInfo
    from dto.log import RequestLogDTO, ResponseLogDTO
    from exception import (
        CustomAssertionError,
        CustomBaseException,
        HTTPRequestFailedError,
        HTTPStatusException,
        HTTPTimeoutException,
        JSONParseError,
        UnknownError,
    )
except Exception as exc:  # pragma: no cover - depends on legacy runtime layout
    _LEGACY_REQUESTER_AVAILABLE = False
    _LEGACY_REQUESTER_IMPORT_ERROR = exc

    class _FallbackLogging:
        @staticmethod
        def get_logger() -> Logger:
            return logging.getLogger(__name__)

    Logging = _FallbackLogging  # type: ignore[assignment]


class HTTPResponse:
    def __init__(self, response: httpx.Response):
        self.headers = dict(response.headers)
        self.status_code = response.status_code
        self.content = response.content

    def text(self) -> str:
        return self.content.decode()

    def json(self) -> dict | list:
        try:
            data = json.loads(self.content)
        except json.JSONDecodeError as error:
            if _LEGACY_REQUESTER_AVAILABLE:
                raise JSONParseError(value=self.content.decode("utf-8"), error=error)
            raise ValueError("failed to parse response JSON") from error
        return data

    def raise_for_status(self):
        if self.status_code < 300:
            return

        try:
            status = HTTPStatus(self.status_code)
            status_message = status.description
        except ValueError:
            status = None
            status_message = f"HTTP status {self.status_code}"

        if _LEGACY_REQUESTER_AVAILABLE:
            assert status is not None
            raise HTTPStatusException(
                status_code=status.value,
                exception_code=ResponseCodeEnum.HTTP_REQUEST_STATUS_ERROR,
                message=status_message,
            )

        raise RuntimeError(status_message)


class HTTPClient:
    _client: httpx.AsyncClient | None = None

    @classmethod
    def connect_client(
        cls,
        read_timeout: float | None,
        write_timeout: float | None,
        connection_timeout: float | None,
        pool_timeout: float | None,
        max_connections: int,
        max_keepalive_connections: int,
        keepalive_expiry: float,
    ) -> httpx.AsyncClient:
        if cls._client is None:
            timeout = httpx.Timeout(
                read=read_timeout,
                write=write_timeout,
                connect=connection_timeout,
                pool=pool_timeout,
            )

            connection_limits = httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
                keepalive_expiry=keepalive_expiry,
            )

            cls._client = httpx.AsyncClient(
                timeout=timeout,
                limits=connection_limits,
                follow_redirects=True,
            )

        return cls._client

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None:
            raise RuntimeError("http connection pool not initialized")
        return cls._client

    @classmethod
    def ensure_client(cls, default_timeout: float | None = None) -> httpx.AsyncClient:
        if cls._client is not None:
            return cls._client

        if default_timeout is None:
            cls._client = httpx.AsyncClient(follow_redirects=True)
        else:
            cls._client = httpx.AsyncClient(
                timeout=default_timeout,
                follow_redirects=True,
            )
        return cls._client

    @classmethod
    async def close_client(cls):
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None


async def send_request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    data: dict | list | None = None,
    json_data: dict | list | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    client = HTTPClient.ensure_client(default_timeout=timeout)
    return await client.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        data=data,
        json=json_data,
        timeout=timeout,
    )


async def post_json(
    url: str,
    *,
    headers: dict | None = None,
    json_data: dict | list | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    return await send_request(
        "POST",
        url,
        headers=headers,
        json_data=json_data,
        timeout=timeout,
    )


if _LEGACY_REQUESTER_AVAILABLE:

    class HTTPRequester:
        def __init__(
            self,
            request_object: Request,
            client: Annotated[httpx.AsyncClient, Depends(HTTPClient.get_client)],
            logger: Annotated[Logger, Depends(Logging.get_logger)],
        ):
            self._request_object = request_object
            self._n_retry = 1

            access_info = AccessInfo.from_request(request_object)
            request_id = access_info.request_id
            self._client = client
            self._client.headers["X-Request-ID"] = request_id
            self._request_id = request_id

            self._enable_logging = False
            self._logger = logger

        def set_logging(self, enable: bool):
            self._enable_logging = enable

        def set_retry(self, retry: int):
            self._n_retry = retry

        def set_default_header(self, key: str, value: str):
            self._client.headers[key] = value

        async def _request(self, method: str, url: str, **kwargs) -> HTTPResponse:
            if self._enable_logging:
                request_log = RequestLogDTO(
                    request_id=self._request_id,
                    url_path=self._request_object.url.path,
                    method=self._request_object.method,
                    target_url=url,
                    target_method=method,
                    **kwargs,
                )
                self._logger.debug(request_log.model_dump(mode="json"))

            response = await self._send(method, url, **kwargs)

            if self._enable_logging:
                response_log = ResponseLogDTO(
                    request_id=self._request_id,
                    url_path=self._request_object.url.path,
                    method=self._request_object.method,
                    target_url=url,
                    target_method=method,
                    status_code=response.status_code,
                    body=response.text(),
                    headers=response.headers,
                )
                self._logger.debug(response_log.model_dump(mode="json"))

            return response

        async def _send(self, method: str, url: str, **kwargs) -> HTTPResponse:
            for index in range(self._n_retry):
                retry = index < (self._n_retry - 1)

                try:
                    _response = await self._client.request(method, url, **kwargs)
                    response = HTTPResponse(_response)
                    return response
                except httpx.TimeoutException as exc:
                    raise HTTPTimeoutException(timeout_exception=exc)
                except httpx.RequestError as err:
                    request_error = HTTPRequestFailedError(err, url, method, retry)
                    if not retry:
                        raise request_error
                    log_dto = request_error.handle_log(self._request_object)
                    self._logger.debug(log_dto.model_dump(mode="json"))
                except (httpx.InvalidURL, httpx.CookieConflict, httpx.StreamError) as error:
                    raise HTTPRequestFailedError(error, url, method)
                except Exception as error:
                    raise UnknownError(error)

            raise CustomAssertionError(
                "cannot reach here - corner error case did not handled"
            )

        async def get(
            self,
            url: str,
            params: dict | None = None,
            headers: dict | None = None,
            cookies: dict | None = None,
            timeout: float | None = None,
        ) -> HTTPResponse:
            response = await self._request(
                "GET",
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=timeout,
            )
            return response

        async def post(
            self,
            url: str,
            headers: dict | None = None,
            data: dict | list | None = None,
            files: dict[str, IO[bytes]] | None = None,
            json: dict | list | None = None,
            timeout: float | None = None,
        ) -> HTTPResponse:
            response = await self._request(
                "POST",
                url,
                headers=headers,
                data=data,
                files=files,
                json=json,
                timeout=timeout,
            )
            return response

        async def patch(
            self,
            url: str,
            headers: dict | None = None,
            data: dict | list | None = None,
            files: dict[str, IO[bytes]] | None = None,
            json: dict | list | None = None,
            timeout: float | None = None,
        ) -> HTTPResponse:
            response = await self._request(
                "PATCH",
                url,
                headers=headers,
                data=data,
                files=files,
                json=json,
                timeout=timeout,
            )
            return response

else:

    class HTTPRequester:
        def __init__(self, *args, **kwargs):
            message = "legacy HTTPRequester dependencies are unavailable in PB runtime"
            if _LEGACY_REQUESTER_IMPORT_ERROR is not None:
                message += f": {_LEGACY_REQUESTER_IMPORT_ERROR}"
            raise RuntimeError(message)
