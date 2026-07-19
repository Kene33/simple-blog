import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, host="127.0.0.1", port=4000)
