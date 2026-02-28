from http import HTTPStatus
from logging import Logger

from fastapi import Request
from fastapi.responses import JSONResponse

from core.access import AccessInfo
from constant.enums import ResponseCodeEnum
from dto.log import ExceptionLogDTO

from .base import JSONResponseException


class AuthError(JSONResponseException):
    def __init__(
        self,
        status_code: int = HTTPStatus.UNAUTHORIZED.value,
        exception_code: ResponseCodeEnum = ResponseCodeEnum.UNAUTHORIZED,
        message: str = HTTPStatus.UNAUTHORIZED.description,
    ):
        self.status = HTTPStatus.UNAUTHORIZED
        super().__init__(
            status_code, exception_code, message, origin_exception=None
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
            origin_type=self.origin_type,
            origin_message=self.origin_message,
            origin_traceback=self.origin_traceback,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        error_log = self.handle_log(request)
        logger.info(error_log.model_dump(mode="json"))
        return super().handle(logger, request)


class NoSessionIdError(AuthError):
    def __init__(self, from_header: bool):
        if from_header:
            message = "no session id in 'Authorization' field in header"
        else:
            message = "no session id in http cookie"

        super().__init__(
            exception_code=ResponseCodeEnum.NO_SESSION_ID, message=message
        )


class InvalidSessionIdError(AuthError):
    def __init__(self):
        super().__init__(
            exception_code=ResponseCodeEnum.INVALID_SESSION_ID,
            message="invalid session id",
        )


class SessionExpiredError(AuthError):
    def __init__(self):
        super().__init__(
            exception_code=ResponseCodeEnum.SESSION_EXPIRED,
            message="session expired - please generate new session",
        )


class LoginFailed(AuthError):
    def __init__(self, error_message: str):
        self.error_message = error_message
        super().__init__(
            exception_code=ResponseCodeEnum.LOGIN_FAILED,
            message="login failed",
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
            origin_type=self.origin_type,
            origin_message=self.origin_message,
            origin_traceback=self.origin_traceback,
        )
        return log_dto

    def handle(self, logger: Logger, request: Request) -> JSONResponse:
        warn_log = self.handle_log(request)
        logger.warning(warn_log.model_dump(mode="json"))
        # AuthError의 handle 메소드 건너뜀 (이중 로깅 방지)
        response = super(AuthError, self).handle(logger, request)
        return response
