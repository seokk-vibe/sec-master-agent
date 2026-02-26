import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Body, FastAPI, Request, Response, applications
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api import api_router, stream_router
from common.config import load_config
from common.logger import Logging
from core.middleware import CustomASGIMiddleware
from core.requester import HTTPClient
from core.time import TimeFactory
from db.mongodb import MongoCollection, MongoConnection, MongoKillSwitchCollection
from db.oracledb import OracleConnection
from db.postgredb import PostgreConnection
from dto.requests import AnyRequestDTO
from dto.responses import HTTPExceptionResponseDTO
from exception import CustomBaseException, RequestParamValidationError

config = load_config()
Logging.setup(config.logger)


@asynccontextmanager
async def fastapi_lifespan(app: FastAPI):
    # logger = Logging.get_logger()
    # logger.info(config)

    # oracle_password = os.getenv("ORACLE_PASSWORD", "")

    # 서버 시작 전 동작 로직

    HTTPClient.connect_client(
        read_timeout=config.http.timeout.read,
        write_timeout=config.http.timeout.write,
        connection_timeout=config.http.timeout.connection,
        pool_timeout=config.http.timeout.pool,
        max_connections=config.http.connection.max_connection,
        max_keepalive_connections=(config.http.connection.max_keepalive_connections),
        keepalive_expiry=config.http.connection.keepalive_expiry,
    )

    # 서버 시작
    yield

    _ = killer_task.cancel()
    await killer_task

    # 서버 종료 전 동작 로직



docs_url = None if not config.show_swagger else "/docs"
redoc_url = None if not config.show_swagger else "/redoc"
app = FastAPI(
    title="RestAPI Ground / by AI",
    lifespan=fastapi_lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    responses={
        500: {"model": HTTPExceptionResponseDTO},
        422: {"model": HTTPExceptionResponseDTO},
    },
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CustomASGIMiddleware)

app.include_router(router=api_router, prefix="/api")
app.include_router(router=stream_router, prefix="/stream")


@app.exception_handler(CustomBaseException)
async def exception_handler(request: Request, exc: CustomBaseException) -> Response:
    logger = Logging.get_logger()
    response = exc.handle(logger, request)
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger = Logging.get_logger()

    error = RequestParamValidationError(validation_error=exc)
    response = error.handle(logger, request)
    return response


@app.get("/Health")
async def health_check():
    return {"time": str(datetime.now())}


if config.test.endpoint.enable:
    # TODO 테스트용
    from core.requester import HTTPRequester  # noqa
    from fastapi import Depends  # noqa
    from common.config import AppConfig  # noqa

    @app.post("/test")
    async def test_endpoint(
        request: Request, body: Annotated[AnyRequestDTO, Body(...)]
    ):
        # body = await request.body()
        content = {
            "header": dict(request.headers),
            "body": body.model_dump(),
            "cookies": request.cookies,
        }
        return content

# swagger ui를 아래에서 요청하지만 폐쇄망 때문에 실패하므로 static 파일을 사용하도록
# https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js
app.mount(
    "/assets",
    StaticFiles(
        directory=os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            os.environ.get(
                "SWAGGER_STATIC_FILE_RELPATH",
                "../share/swagger-ui-master/dist",
            ),
        )
    ),
    name="assets",
)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html(openapi_url, title, **kwargs):
    return get_swagger_ui_html(
        openapi_url=(app.openapi_url if app.openapi_url is not None else openapi_url),
        title="Custom Swagger UI",
        # *args,
        **kwargs,
        swagger_favicon_url="",
        swagger_js_url="/assets/swagger-ui-bundle.js",
        swagger_css_url="/assets/swagger-ui.css",
    )


setattr(applications, "get_swagger_ui_html", custom_swagger_ui_html)


if __name__ == "__main__":
    # TODO guicorn으로 교체
    import uvicorn

    uvicorn.run(app="main:app", host="0.0.0.0", port=18080, reload=False)
    # uvicorn.run(
    #     app="main:app",
    #     host="0.0.0.0",
    #     port=8097,
    #     reload=False,
    #     ssl_certfile="ssl/cert.pem",
    #     ssl_keyfile="ssl/nopass_key.pem",
    # )
