from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from PB.api import api_router
from PB.core.requester import HTTPClient
from PB.core.settings import load_settings

settings = load_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 초기 보일러플레이트: 운영 전에는 프론트 도메인으로 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": settings.app_version}


@app.on_event("shutdown")
async def close_http_client_pool() -> None:
    await HTTPClient.close_client()
