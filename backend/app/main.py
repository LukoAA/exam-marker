"""FastAPI app factory: CORS + routers."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth


def create_app() -> FastAPI:
    app = FastAPI(title="ExamMarker API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)

    return app


app = create_app()
