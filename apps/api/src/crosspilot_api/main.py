"""FastAPI 应用入口。路由只做编排，规则一律下沉到 domain/。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers.evidence import router as evidence_router
from .services.safety_gate_retrieval import warm_cache

#: 允许浏览器端直连的开发前端源。Nuxt dev(3000) 与 build 预览同源。
#: 仅本机演示用，不做通配放开；生产若变更前端端口需同步此表。
CORS_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """服务启动时预热证据快照缓存，避免每次请求重读数据区。"""
    warm_cache()
    yield


app = FastAPI(title="CrossPilot 2.0 API", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=[],
)
app.include_router(evidence_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_mode": settings.data_mode}
