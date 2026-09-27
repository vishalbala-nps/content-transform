import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core import jobs
from app.core.config import get_settings
from app.db.models import init_db

# The React app's production build (`npm run build` in web/). In development
# run `npm run dev` instead; Vite serves the UI and proxies /api to this server.
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()  # fails here, not on the first job, if LLM_PROVIDER is wrong
    log.info("model calls go to %s, model %s", settings.llm_provider, settings.llm_model)
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
