from fastapi import FastAPI
from .routes import playlists
from .routes import tracks
from .routes import recommendations

app = FastAPI(title="Music Discovery API", version="v1")

app.include_router(playlists.router)
app.include_router(recommendations.router)
# include other routers

# root
@app.get("/")
def root():
    return {"message":"Music Discovery API — FastAPI"}
