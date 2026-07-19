import uvicorn

from src.core.config import get_settings
from src.main import app


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("main:app", reload=settings.reload, host=settings.host, port=settings.port)
