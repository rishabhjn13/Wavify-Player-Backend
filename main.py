import time
import uuid
from contextlib import asynccontextmanager
from utils.logger import get_logger

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from database import init_db
from routes.playlists import router as playlists_router
from routes.search import router as search_router
from routes.audio import router as audio_router
from routes.download import router as download_router
from routes.songs import router as songs_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Wavify backend...")
    try:
        init_db()
        logger.info("Database initialised successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialise database: {e}", exc_info=True)
        raise  # Abort startup — no point running without a DB

    yield  # App runs here

    # Shutdown
    logger.info("Wavify backend shutting down.")

app = FastAPI(
    title="Wavify Backend",
    description="Full-stack music streaming backend",
    version="1.0.0",
    lifespan=lifespan
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    start = time.perf_counter()
    logger.info(f"[{request_id}] {request.method} {request.url.path}")

    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(f"[{request_id}] Unhandled exception in middleware: {exc}", exc_info=True)
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    if duration_ms > 3000:
        logger.warning(f"[{request_id}] Slow request: {request.url.path} took {duration_ms:.0f}ms")
    else:
        logger.info(f"[{request_id}] {response.status_code} — {duration_ms:.0f}ms")

    response.headers["X-Request-ID"] = request_id
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        f"[{request_id}] HTTP {exc.status_code} on {request.url.path}: {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
        "success": False,
        "error": exc.detail,
        "code": getattr(exc, "code", _status_to_code(exc.status_code)),
        "request_id": request_id,
    },
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"[{request_id}] Unexpected error on {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An unexpected error occurred. Please try again.",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
    },
)

def _status_to_code(status: int) -> str:
    """Map common HTTP status codes to readable error codes."""
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        503: "SERVICE_UNAVAILABLE",
    }.get(status, "HTTP_ERROR")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(playlists_router)
app.include_router(search_router)
app.include_router(audio_router)
app.include_router(download_router)
app.include_router(songs_router)

# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Wavify Backend is running 🚀"}

@app.get("/health", tags=["meta"])
def health_check():
    """Lightweight liveness probe — useful for scripts and future deployment."""
    return {"status": "ok", "version": app.version}