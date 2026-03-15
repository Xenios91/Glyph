from fastapi import FastAPI
from app.routers import binaries_api, predictions_api

app = FastAPI()
app.include_router(binaries_api.router)
app.include_router(predictions_api.router)