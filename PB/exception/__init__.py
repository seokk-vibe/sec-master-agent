from .auth import (
    AuthError,
    InvalidSessionIdError,
    LoginFailed,
    NoSessionIdError,
    SessionExpiredError,
)
from .base import CustomAssertionError, CustomBaseException, UnknownError
from .http import (
    BadRequest,
    Banned,
    Forbidden,
    HTTPRequestFailedError,
    HTTPStatusException,
    HTTPTimeoutException,
    NotFound,
    QueryLimitExceed,
    RequestParamValidationError,
    TRRequestFailedError,
    UnprocessableEntity,
)
from .module import (
    ModuleServerStatusError,
    NoRequiredFieldError,
    # OutputGuardrailException,
)
from .mongo import MongoError, MongoInvalidObjectId
from .oracle import OracleError
from .postgre import PostgreError
from .system import InvalidValue, JSONParseError, SystemKilledByAdmin

__all__ = [
    # base
    "CustomBaseException",
    "UnknownError",
    "CustomAssertionError",
    # auth
    "NoSessionIdError",
    "InvalidSessionIdError",
    "SessionExpiredError",
    "AuthError",
    "LoginFailed",
    # http
    "TRRequestFailedError",
    "HTTPRequestFailedError",
    "HTTPStatusException",
    "HTTPTimeoutException",
    "NotFound",
    "BadRequest",
    "Forbidden",
    "QueryLimitExceed",
    "Banned",
    "UnprocessableEntity",
    "RequestParamValidationError",
    # module
    "ModuleServerStatusError",
    "NoRequiredFieldError",
    # "OutputGuardrailException",
    # mongo
    "MongoError",
    "MongoInvalidObjectId",
    # oracle
    "OracleError",
    # postgre
    "PostgreError",
    # system
    "InvalidValue",
    "JSONParseError",
    "SystemKilledByAdmin",
]
