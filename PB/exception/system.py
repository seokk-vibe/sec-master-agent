from json import JSONDecodeError
from typing import Any, Type
from http import HTTPStatus
from logging import Logger

from fastapi import Request
from fastapi.responses import JSONResponse

from core.access import AccessInfo
from constant.enums import ResponseCodeEnum
from dto.log import ExceptionLogDTO

from .base import JSONResponseException


class InvalidValue(JSONResponseException):
    def __init__(
        self,
        value: Any,
        target_type: Type,
        validation_error: Exception | None = None,
    ):
        self.value = value
        self.target_type = target_type

        self.status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=self.status.value,
            exception_code=ResponseCodeEnum.INTERNAL_ERROR,
            message=self.status.description,
            origin_exception=validation_error,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        message = "invalid value for type "
        message += f"{self.target_type.__name__} - {self.value}"

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message=message,
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


class JSONParseError(JSONResponseException):
    def __init__(self, value: str, error: JSONDecodeError):
        self.value = value
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
            message="json decode error",
            url_path=request.url.path,
            method=request.method,
            error_type=self.__class__.__name__,
            origin_type=self.origin_type,
            origin_message=self.origin_message,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        error_log = self.handle_log(request)
        logger.error(error_log.model_dump(mode="json"))

        response = super().handle(logger, request)
        return response


class SystemKilledByAdmin(JSONResponseException):
    def __init__(self):
        self.status = HTTPStatus.INTERNAL_SERVER_ERROR
        super().__init__(
            status_code=self.status.value,
            exception_code=ResponseCodeEnum.SERVICE_KILLED,
            message=self.status.description,
            origin_exception=None,
        )

    def handle_log(self, request: Request) -> ExceptionLogDTO:
        access_info = AccessInfo.from_request(request)

        log_dto = ExceptionLogDTO(
            request_id=access_info.request_id,
            service_label=access_info.service_label,
            exception_code=self.exception_code,
            message="kill switch on",
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
