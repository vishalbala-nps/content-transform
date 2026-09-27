import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

# The React app's production build (`npm run build` in web/). In development
# run `npm run dev` instead; Vite serves the UI and proxies /api to this server.
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")

app = FastAPI(title="content-transform")
app.include_router(router)
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
