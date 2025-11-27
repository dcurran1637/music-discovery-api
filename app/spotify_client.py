import os, base64, time
import httpx

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TOKEN = None
TOKEN_EXPIRES = 0

async def get_spotify_token():
    global TOKEN, TOKEN_EXPIRES
    if TOKEN and TOKEN_EXPIRES - 30 > time.time():
        return TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        return None
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type":"client_credentials"},
            headers={"Authorization": f"Basic {auth}"}
        )
        r.raise_for_status()
        data = r.json()
        TOKEN = data["access_token"]
        TOKEN_EXPIRES = time.time() + data["expires_in"]
        return TOKEN

async def get_track(track_id):
    token = await get_spotify_token()
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.spotify.com/v1/tracks/{track_id}", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            return r.json()
        return None
