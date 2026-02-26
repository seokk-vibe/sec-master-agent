from abc import abstractmethod, ABC
from traceback import extract_tb
from types import TracebackType
from http import HTTPStatus
from logging import Logger

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from core.access import AccessInfo
from dto.log import ExceptionLogDTO
from dto.responses import HTTPExceptionResponseDTO
from constant.enums import ServiceLabelEnum, ResponseCodeEnum


class CustomBaseException(Exception, ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    def handle_log(self, request: Request) -> ExceptionLogDTO: ...

    @abstractmethod
    def handle(self, logger: Logger, request: Request) -> Response: ...

    @staticmethod
    def get_service_label(request: Request) -> ServiceLabelEnum:
        access_info = AccessInfo.from_request(request)
        return access_info.service_label

    def get_traceback_logs(self, tb: TracebackType | None) -> list[str]:
        stack_summary = extract_tb(tb)
        logs = stack_summary.format()
        return logs


class JSONResponseException(CustomBaseException):
    def __init__(
        self,
        status_code: int,
        exception_code: ResponseCodeEnum,
        message: str,
        origin_exception: Exception | None,
        *args,
        **kwargs,
    ):
        self.status_code = status_code
        self.exception_code = exception_code
        self.message = message
        self.origin_exception = origin_exception

        super().__init__(*args, **kwargs)

    @property
    def content(self) -> dict:
        content = HTTPExceptionResponseDTO(
            code=self.exception_code, message=self.message
        )
        return content.model_dump(mode="json")

    @property
    def origin_type(self) -> str:
        if self.origin_exception is None:
            return ""

        return self.origin_exception.__class__.__name__

    @property
    def origin_message(self) -> str:
        if self.origin_exception is None:
            return ""

        return str(self.origin_exception)

    @property
    def origin_traceback(self) -> list[str]:
        if self.origin_exception is None:
            return []

        return self.get_traceback_logs(self.origin_exception.__traceback__)

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
            origin_type=self.origin_type,
            origin_message=self.origin_message,
            origin_traceback=self.origin_traceback,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        label = self.get_service_label(request)
        match (label):
            case ServiceLabelEnum.MTS:
                response = JSONResponse(status_code=200, content=self.content)
            case _:
                response = JSONResponse(
                    status_code=self.status_code, content=self.content
                )
        return response


class UnknownError(JSONResponseException):
    def __init__(self, error: Exception):
        self.status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=self.status.value,
            exception_code=ResponseCodeEnum.INTERNAL_ERROR,
            message=self.status.description,
            origin_exception=error,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message="unknown error occured need to handle",
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
            origin_message=self.origin_message,
            origin_type=self.origin_type,
            origin_traceback=self.origin_traceback,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        error_log = self.handle_log(request)
        logger.error(error_log.model_dump(mode="json"))
        response = super().handle(logger, request)
        return response


class CustomAssertionError(JSONResponseException):
    def __init__(self, message: str):
        self.log_message = message
        self.status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=self.status.value,
            exception_code=ResponseCodeEnum.INTERNAL_ERROR,
            message=self.status.description,
            origin_exception=None,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message=f"assertion failed - {self.log_message}",
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
            origin_type=self.origin_type,
            origin_message=self.origin_message,
            origin_traceback=self.origin_traceback,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        error_log = self.handle_log(request)
        logger.error(error_log.model_dump(mode="json"))
        response = super().handle(logger, request)
        return response
