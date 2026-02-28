from http import HTTPStatus
from logging import Logger

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from httpx import (
    CookieConflict,
    InvalidURL,
    RequestError,
    StreamError,
    TimeoutException,
)

from constant.enums import ResponseCodeEnum
from core.access import AccessInfo
from dto.log import ExceptionLogDTO

from .base import JSONResponseException


class TRRequestFailedError(JSONResponseException):
    def __init__(
        self, tr_url: str, error_code: str, error_type: str, error_message: str
    ):
        self.tr_url = tr_url
        self.error_code = error_code
        self.error_type = error_type
        self.error_message = error_message

        status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=status.value,
            exception_code=ResponseCodeEnum.TR_FAILED_ERROR,
            message=status.description,
            origin_exception=None,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message=f"failed to send tr request - {self.tr_url}",
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
            origin_type=self.error_type,
            origin_message=self.error_message,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        error_log = self.handle_log(request)
        logger.error(error_log.model_dump(mode="json"))
        response = super().handle(logger, request)
        return response


class HTTPRequestFailedError(JSONResponseException):
    def __init__(
        self,
        error: RequestError | InvalidURL | CookieConflict | StreamError,
        url: str,
        method: str,
        retry: bool = False,
    ):
        self.error_type = error.__class__.__name__
        self.error_str = str(error)
        self.error_traceback = self.get_traceback_logs(error.__traceback__)
        self.url = url
        self.method = method
        self.retry = retry

        self.status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=self.status.value,
            exception_code=ResponseCodeEnum.INTERNAL_ERROR,
            message=self.status.description,
            origin_exception=error,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        message = f"failed to send request to {self.url}"
        if self.retry:
            message += " - retry..."

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message=message,
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
            origin_type=self.error_type,
            origin_message=self.error_str,
            origin_traceback=self.error_traceback,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        error_log = self.handle_log(request)
        logger.error(error_log.model_dump(mode="json"))
        response = super().handle(logger, request)
        return response


class HTTPTimeoutException(JSONResponseException):
    def __init__(self, timeout_exception: TimeoutException):
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=status.value,
            exception_code=ResponseCodeEnum.INTERNAL_ERROR,
            message=status.description,
            origin_exception=timeout_exception,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message=self.message,
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        info_log = self.handle_log(request)
        logger.info(info_log.model_dump(mode="json"))
        response = super().handle(logger, request)
        return response


class HTTPStatusException(JSONResponseException):
    def __init__(
        self, status_code: int, exception_code: ResponseCodeEnum, message: str
    ):
        super().__init__(status_code, exception_code, message, origin_exception=None)

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message=self.message,
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        info_log = self.handle_log(request)
        logger.info(info_log.model_dump(mode="json"))
        response = super().handle(logger, request)
        return response


class NotFound(HTTPStatusException):
    def __init__(self, resource: str = "", source: str = ""):
        status = HTTPStatus.NOT_FOUND
        self.resource = resource
        self.source = source

        message = f"{self.resource} not found "
        message += f"at {self.source}" if self.source else ""

        super().__init__(
            status_code=status.value,
            exception_code=ResponseCodeEnum.NOT_FOUND,
            message=message,
        )


class BadRequest(HTTPStatusException):
    def __init__(self, message: str):
        status = HTTPStatus.BAD_REQUEST
        super().__init__(
            status_code=status.value,
            exception_code=ResponseCodeEnum.BAD_REQUEST,
            message=message,
        )


class Forbidden(HTTPStatusException):
    def __init__(
        self,
        message: str,
        exception_code: ResponseCodeEnum = ResponseCodeEnum.FORBIDDEN,
    ):
        status = HTTPStatus.FORBIDDEN
        super().__init__(
            status_code=status.value,
            exception_code=exception_code,
            message=message,
        )


class QueryLimitExceed(Forbidden):
    def __init__(self):
        super().__init__(
            message="query daily limit exceeded",
            exception_code=ResponseCodeEnum.MESSAGE_LIMIT_EXCEED,
        )


class Banned(Forbidden):
    def __init__(self):
        super().__init__(
            message="user banned",
            exception_code=ResponseCodeEnum.BANNED,
        )


class UnprocessableEntity(HTTPStatusException):
    def __init__(
        self,
        message: str,
        exception_code: ResponseCodeEnum = (ResponseCodeEnum.UNPROCESSABLE_ENTITY),
    ):
        status = HTTPStatus.UNPROCESSABLE_ENTITY
        super().__init__(
            status_code=status.value,
            exception_code=exception_code,
            message=message,
        )


class RequestParamValidationError(UnprocessableEntity):
    def __init__(self, validation_error: RequestValidationError):
        error_messages = [
            f"{err['msg']} - {err['loc']}" for err in validation_error.errors()
        ]
        super().__init__(
            exception_code=ResponseCodeEnum.UNPROCESSABLE_ENTITY,
            message=",".join(error_messages),
        )
