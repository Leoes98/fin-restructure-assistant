from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("FastAPI application started")
    yield


app = FastAPI(title="Fin Restructure Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
