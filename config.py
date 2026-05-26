import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database.db")
SEEDS_DIR = os.path.join(BASE_DIR, "seeds")
UPLOAD_DIR = "static/thumbnails"