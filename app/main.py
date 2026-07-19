from fastapi import FastAPI

from app.core.lifespan import lifespan


def create_app() -> FastAPI:
    return FastAPI(title="Simple Blog API", version="0.1.0", lifespan=lifespan)


app = create_app()
