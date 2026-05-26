from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routes.playlists import router as playlists_router
from routes.search import router as search_router
from routes.audio import router as audio_router

app = FastAPI(title="Spotify Clone Audio Resolver with Cache")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB
init_db()

# Include routers
app.include_router(playlists_router)
app.include_router(search_router)
app.include_router(audio_router)

@app.get("/")
def root():
    return {"message": "Wavify Backend is running 🚀"}