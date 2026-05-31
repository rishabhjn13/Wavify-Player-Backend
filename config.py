import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_FILE = str(os.getenv("DB_FILE", BASE_DIR / "database.db"))
SEEDS_DIR = str(os.getenv("SEEDS_DIR", BASE_DIR / "seeds"))

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
UPLOAD_DIR = str(os.getenv("UPLOAD_DIR", BASE_DIR / "static" / "thumbnails"))
DOWNLOADS_DIR = str(os.getenv("DOWNLOADS_DIR", BASE_DIR / "static" / "downloads"))

# ---------------------------------------------------------------------------
# Audio / yt-dlp
# ---------------------------------------------------------------------------

# Max retries for yt-dlp extractions before giving up
YDL_MAX_RETRIES: int = int(os.getenv("YDL_MAX_RETRIES", 3))

# Seconds before a cached stream URL is considered stale
STREAM_URL_TTL: int = int(os.getenv("STREAM_URL_TTL", 3600))  # 1 hour

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

ENV = os.getenv("APP_ENV", "development")  # "development" | "production"
IS_DEV = ENV == "development"

ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

# ---------------------------------------------------------------------------
# Validation — fail fast at startup if the environment is broken
# ---------------------------------------------------------------------------

def validate_config() -> None:
    """
    Call once at startup (from lifespan) to catch misconfigured
    environments before they cause cryptic runtime errors.
    """
    errors: list[str] = []

    if not os.path.exists(BASE_DIR):
        errors.append(f"BASE_DIR does not exist: {BASE_DIR}")

    if YDL_MAX_RETRIES < 1:
        errors.append(f"YDL_MAX_RETRIES must be >= 1, got {YDL_MAX_RETRIES}")

    if STREAM_URL_TTL < 60:
        errors.append(f"STREAM_URL_TTL seems too low ({STREAM_URL_TTL}s). Minimum recommended is 60s.")
    
    if not ALLOWED_ORIGINS:
        errors.append("ALLOWED_ORIGINS is empty — CORS will block all requests.")

    # Ensure required directories exist, create them if not
    for name, path in [("UPLOAD_DIR", UPLOAD_DIR), ("DOWNLOADS_DIR", DOWNLOADS_DIR)]:
        os.makedirs(path, exist_ok=True)

    if errors:
        raise EnvironmentError("Config validation failed:\n" + "\n".join(f"  • {e}" for e in errors))

# ---------------------------------------------------------------------------
# Debug helper
# ---------------------------------------------------------------------------

def print_config() -> None:
    """Log the active config — call in dev to verify env vars are picked up."""
    print(f"""
    ╔══════════════════════════════════════╗
    ║         Wavify Config ({ENV:<12})║
    ╠══════════════════════════════════════╣
    BASE_DIR        : {BASE_DIR}
    DB_FILE         : {DB_FILE}
    SEEDS_DIR       : {SEEDS_DIR}
    UPLOAD_DIR      : {UPLOAD_DIR}
    DOWNLOADS_DIR   : {DOWNLOADS_DIR}
    STREAM_URL_TTL  : {STREAM_URL_TTL}s
    YDL_MAX_RETRIES : {YDL_MAX_RETRIES}
    ALLOWED_ORIGINS : {ALLOWED_ORIGINS}
    ╚══════════════════════════════════════╝
    """)
