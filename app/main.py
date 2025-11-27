from fastapi import FastAPI
from .routes import playlists
from .routes import tracks
from .routes import recommendations
from .routes import auth_routes

app = FastAPI(title="Music Discovery API", version="v1")

app.include_router(playlists.router)
app.include_router(recommendations.router)
app.include_router(auth_routes.router)

# root
@app.get("/")
def root():
    return {"message":"Music Discovery API — FastAPI"}
