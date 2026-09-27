from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="content-transform")
app.include_router(router)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
