import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core import jobs
from app.db.models import init_db

# The React app's production build (`npm run build` in web/). In development
# run `npm run dev` instead; Vite serves the UI and proxies /api to this server.
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    jobs.requeue_interrupted()
    worker = asyncio.create_task(jobs.worker())
    yield
    worker.cancel()
    with suppress(asyncio.CancelledError):
        await worker


app = FastAPI(title="content-transform", lifespan=lifespan)
app.include_router(router)
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
