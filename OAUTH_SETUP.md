# OAuth 2.0 Integration with Spotify - Setup Guide

## Overview

This Music Discovery API now uses **OAuth 2.0 Authorization Code Flow** for Spotify authentication. This allows users to securely grant your application access to their Spotify account without sharing their credentials.

## Architecture

### OAuth 2.0 Flow

```
1. User clicks "Login with Spotify"
   ↓
2. User is redirected to Spotify authorization page
   ↓
3. User grants permission to your app
   ↓
4. Spotify redirects back to your app with authorization code
   ↓
5. Backend exchanges code for access & refresh tokens
   ↓
6. Backend creates JWT containing Spotify tokens
   ↓
7. Client uses JWT for subsequent API requests
   ↓
8. API uses Spotify access token to make requests on user's behalf
```

## Setup Instructions

### 1. Register Your Application with Spotify

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account (create one if needed)
3. Click "Create an App"
4. Accept the terms and create the app
5. You'll get:
   - **Client ID**
   - **Client Secret** (keep this secret!)

### 2. Configure Redirect URI

In your Spotify app settings:
1. Go to "Edit Settings"
2. Add Redirect URI: `http://localhost:8000/api/auth/callback` (for development)
3. For production, use your actual domain: `https://yourdomain.com/api/auth/callback`

### 3. Set Environment Variables

Create a `.env` file in your project root:

```bash
# Spotify OAuth
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback

# JWT Configuration
JWT_SECRET=your_super_secret_jwt_key_here

# Optional: Redis for caching (if not set, caching is skipped)
REDIS_URL=redis://localhost:6379
```

### 4. Update Your `.env` File

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://localhost:8000/api/auth/callback"
export JWT_SECRET="your_jwt_secret_key"
```

## API Endpoints

### Authentication Endpoints

#### 1. **Initiate Login**
```
GET /api/auth/login?user_id=<unique_user_id>
```

**Response:** Redirects to Spotify authorization page

**Example:**
```bash
curl "http://localhost:8000/api/auth/login?user_id=user123"
```

---

#### 2. **OAuth Callback (Spotify redirects here)**
```
GET /api/auth/callback?code=<auth_code>&state=<state>
```

**Response:** JWT token
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "user123"
}
```

---

#### 3. **Get Current User Profile**
```
GET /api/auth/me?authorization=Bearer%20<jwt_token>
```

**Response:**
```json
{
  "id": "spotify_user_id",
  "display_name": "User Name",
  "email": "user@example.com",
  "followers": {"href": null, "total": 10},
  "external_urls": {"spotify": "https://open.spotify.com/user/..."},
  "uri": "spotify:user:..."
}
```

---

#### 4. **Refresh Spotify Token**
```
POST /api/auth/refresh?refresh_token=<refresh_token>
```

**Response:**
```json
{
  "access_token": "new_access_token",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

#### 5. **Logout**
```
GET /api/auth/logout?user_id=<user_id>
```

**Response:**
```json
{
  "message": "User user123 logged out. Please discard the token.",
  "status": "success"
}
```

---

### Protected Endpoints

#### Get Recommendations (requires JWT token)
```
GET /api/discover/recommendations?genres=rock,pop&min_popularity=70&released_after=2023-01-01
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "recommendedTracks": [
    {
      "trackId": "track123",
      "title": "Song Title",
      "artist": "Artist Name",
      "genres": ["rock", "indie"],
      "album": {
        "name": "Album Name",
        "release_date": "2023-06-15"
      },
      "popularity": 75,
      "previewUrl": "https://..."
    }
  ]
}
```

## Frontend Integration Example

### JavaScript/React

```javascript
// 1. Redirect user to login
function loginWithSpotify(userId) {
  window.location.href = `http://localhost:8000/api/auth/login?user_id=${userId}`;
}

// 2. Extract token from callback (handle redirect from Spotify)
function getTokenFromURL() {
  const params = new URLSearchParams(window.location.search);
  return params.get('access_token');
}

// 3. Store token in localStorage
localStorage.setItem('spotify_token', jwtToken);

// 4. Use token in API requests
async function getRecommendations(genres) {
  const token = localStorage.getItem('spotify_token');
  const response = await fetch(
    `http://localhost:8000/api/discover/recommendations?genres=${genres}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  return response.json();
}

// 5. Logout
function logout(userId) {
  localStorage.removeItem('spotify_token');
  fetch(`http://localhost:8000/api/auth/logout?user_id=${userId}`);
}
```

### Python Client Example

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# 1. Login (redirect user)
def login(user_id):
    auth_url = f"{BASE_URL}/api/auth/login?user_id={user_id}"
    print(f"Redirect user to: {auth_url}")

# 2. Handle callback and get token (in real app, Spotify redirects to your backend)
def handle_callback(code, state):
    response = requests.get(
        f"{BASE_URL}/api/auth/callback",
        params={"code": code, "state": state}
    )
    token_data = response.json()
    return token_data['access_token']

# 3. Get recommendations
def get_recommendations(token, genres="rock,pop"):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/discover/recommendations",
        params={"genres": genres},
        headers=headers
    )
    return response.json()

# 4. Get user profile
def get_user_profile(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/auth/me",
        params={"authorization": f"Bearer {token}"},
        headers=headers
    )
    return response.json()

# Example usage
if __name__ == "__main__":
    user_id = "my_user_123"
    
    # Start login flow
    login(user_id)
    
    # After user authorizes (you get code from redirect)
    code = "your_auth_code_here"
    state = "your_state_here"
    
    token = handle_callback(code, state)
    print(f"Token: {token}")
    
    # Get recommendations
    recs = get_recommendations(token)
    print(json.dumps(recs, indent=2))
```

## Token Management

### JWT Token Structure

The JWT token contains:
```json
{
  "user_id": "user123",
  "spotify_access_token": "spotify_token_here",
  "spotify_refresh_token": "spotify_refresh_token_here",
  "exp": 1700000000,
  "iat": 1699996400
}
```

### Token Expiration & Refresh

1. **JWT expires in:** 3600 seconds (1 hour, same as Spotify token)
2. **To refresh:** Use the `spotify_refresh_token` from the JWT
3. **Refresh endpoint:** `POST /api/auth/refresh?refresh_token=<refresh_token>`
4. **New token:** You'll get a new access token without needing user re-authorization

### Security Best Practices

1. **Never expose Client Secret** in frontend code
2. **Store tokens securely:**
   - LocalStorage (simple, but vulnerable to XSS)
   - Secure HttpOnly cookies (recommended)
   - In-memory (safest, but lost on refresh)
3. **Use HTTPS in production** for all API calls
4. **Refresh tokens before expiration** to maintain seamless UX
5. **Implement token rotation** for enhanced security

## Scopes Requested

The app requests these Spotify scopes:
- `user-read-private` - Access user profile data
- `user-read-email` - Access user email
- `user-library-read` - Read user's saved tracks
- `playlist-modify-public` - Create/edit public playlists
- `playlist-modify-private` - Create/edit private playlists
- `user-read-playback-state` - Read playback state

You can modify these in `app/oauth.py` in the `generate_auth_url()` function.

## Testing the Integration

### 1. Test Login Flow
```bash
# Redirect to this URL in your browser
curl -L "http://localhost:8000/api/auth/login?user_id=test_user"
```

### 2. Test Callback (manually)
```bash
# After you get code and state from callback
curl "http://localhost:8000/api/auth/callback?code=<code>&state=<state>"
```

### 3. Test Recommendations
```bash
# Use the JWT token from callback response
curl -H "Authorization: Bearer <jwt_token>" \
  "http://localhost:8000/api/discover/recommendations?genres=rock"
```

### 4. Test User Profile
```bash
curl "http://localhost:8000/api/auth/me?authorization=Bearer%20<jwt_token>"
```

## Troubleshooting

### Issue: "Spotify Client ID not configured"
- **Solution:** Make sure `SPOTIFY_CLIENT_ID` is set in environment variables

### Issue: "Invalid redirect_uri"
- **Solution:** Ensure redirect URI in code matches exactly what you set in Spotify Dashboard

### Issue: "Failed to exchange code for token"
- **Solution:** 
  - Check if Client Secret is correct
  - Verify code hasn't expired (valid for 10 minutes)
  - Check if Authorization header has correct format

### Issue: "Token expired"
- **Solution:** Use refresh token to get new access token

## Production Deployment Checklist

- [ ] Set `SPOTIFY_REDIRECT_URI` to your production domain
- [ ] Use strong `JWT_SECRET` (generate with `openssl rand -hex 32`)
- [ ] Enable HTTPS everywhere
- [ ] Store secrets in secure vault (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] Implement token storage in secure HttpOnly cookies
- [ ] Add rate limiting to auth endpoints
- [ ] Monitor token refresh failures
- [ ] Set up proper logging and error tracking
- [ ] Implement CSRF protection
- [ ] Add state parameter validation

## Files Created/Modified

### New Files:
- `app/oauth.py` - OAuth 2.0 logic
- `app/routes/auth_routes.py` - OAuth endpoints

### Modified Files:
- `app/main.py` - Added auth routes
- `app/auth.py` - Updated token verification
- `app/spotify_client.py` - Updated to use user's OAuth token
- `app/routes/recommendations.py` - Updated to use OAuth tokens

## References

- [Spotify Web API Authorization Guide](https://developer.spotify.com/documentation/general/guides/authorization/)
- [Spotify OAuth 2.0 Scopes](https://developer.spotify.com/documentation/general/guides/scopes/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT Introduction](https://jwt.io/introduction)
