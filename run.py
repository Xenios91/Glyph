from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import binaries_api, predictions_api, views


def create_app() -> FastAPI:
    app = FastAPI()

    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(views.router)
    app.include_router(binaries_api.router)
    app.include_router(predictions_api.router)

    return app


app = create_app()
