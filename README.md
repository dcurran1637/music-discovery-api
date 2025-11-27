# music-discovery-api
How to use the API (quick)
--------------------------
1. Install dependencies and set environment variables:

```bash
pip install -r requirements.txt
export SPOTIFY_CLIENT_ID="d589749d63f14861bfdb5a46e66d9826"
export SPOTIFY_CLIENT_SECRET="6160cb16978d46d2b9f9df75c8465cb1"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8000/api/auth/callback"
export JWT_SECRET="67bd32444f83f1ba"
```

2. Start the server:

```bash
python -m uvicorn app.main:app --reload
```

3. Authenticate a user with Spotify (Authorization Code Flow):

- Open in a browser (or `curl -L`) to begin login and authorize the app:

```text
GET http://localhost:8000/api/auth/login?user_id=<your_user_id>
```

- After authorizing, Spotify redirects to `/api/auth/callback?code=...&state=...`. The server exchanges that `code` and returns a JSON object containing a JWT in `access_token`.

4. Use the returned JWT to call protected endpoints. Add this header to requests:

```
Authorization: Bearer <jwt_token>
```

Example: Get recommendations filtered by genre, popularity and release date

```bash
curl -H "Authorization: Bearer <jwt_token>" \
	"http://localhost:8000/api/discover/recommendations?genres=rock,pop&min_popularity=60&released_after=2023-01-01"
```

Example: Get current Spotify profile (using the JWT returned at callback)

```bash
curl "http://localhost:8000/api/auth/me?authorization=Bearer%20<jwt_token>"
```

Testing
-------
Run the test suite:

```bash
python -m pytest tests/ -v
```

Notes
-----
- The development redirect URI must match the Spotify app setting exactly: `http://localhost:8000/api/auth/callback`.
- In production use HTTPS and secure token storage (HttpOnly cookies or server-side storage). Rotate and refresh tokens as needed.

