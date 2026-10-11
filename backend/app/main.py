from fastapi import FastAPI

from app.api import router

app = FastAPI(title="TileMuse")
app.include_router(router, prefix="/api")
