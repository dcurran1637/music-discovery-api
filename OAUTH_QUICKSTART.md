# OAuth 2.0 Spotify Integration - Quick Start Guide

## What Changed?

Your Music Discovery API now supports **OAuth 2.0 authentication with Spotify**. This means users can securely log in with their Spotify accounts, and your app can access their music data and preferences with their explicit permission.

## Key Features Added

✅ **Spotify OAuth 2.0 Authorization Code Flow**
- Secure user authentication via Spotify
- No need to handle user passwords
- Users can revoke access anytime

✅ **JWT Token Management**
- JWT tokens contain Spotify access/refresh tokens
- Automatic token refresh capabilities
- Secure token-based API access

✅ **User Profile Access**
- Get current user's Spotify profile
- Access user's name, email, followers, etc.

✅ **Genre Filtering with User Tokens**
- Recommendations now use the user's authenticated Spotify token
- Properly scoped access to user-specific resources

## Quick Setup

### 1. Register Your App with Spotify

1. Go to https://developer.spotify.com/dashboard
2. Create a new app
3. Get your **Client ID** and **Client Secret**
4. Set Redirect URI to: `http://localhost:8000/api/auth/callback`

### 2. Set Environment Variables

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://localhost:8000/api/auth/callback"
export JWT_SECRET="your_secret_key"
```

### 3. Start the Server

```bash
python -m uvicorn app.main:app --reload
```

### 4. Test the OAuth Flow

```bash
# 1. Send user to login
curl "http://localhost:8000/api/auth/login?user_id=my_user_123"

# This redirects to Spotify. After user authorizes:
# Spotify redirects back to: /api/auth/callback?code=<code>&state=<state>

# 2. Get your token (happens automatically in the callback)
# Response: {"access_token": "jwt_token", "token_type": "bearer", ...}

# 3. Use token for API requests
curl -H "Authorization: Bearer <jwt_token>" \
  "http://localhost:8000/api/discover/recommendations?genres=rock"

# 4. Get user profile
curl "http://localhost:8000/api/auth/me?authorization=Bearer%20<jwt_token>"
```

## New API Endpoints

### Authentication

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/login` | GET | Start Spotify OAuth login |
| `/api/auth/callback` | GET | Handle Spotify callback (automatic) |
| `/api/auth/me` | GET | Get current user profile |
| `/api/auth/refresh` | POST | Refresh expired token |
| `/api/auth/logout` | GET | Logout user |

### Protected Endpoints (require JWT)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/discover/recommendations` | GET | Get music recommendations with filters |
| `/api/playlists` | GET/POST | Playlist management |

## OAuth Flow Diagram

```
┌─────────────┐
│   Your App  │
└──────┬──────┘
       │
       │ 1. User clicks "Login with Spotify"
       │
       ├──────────────────────────────────────┐
       │ 2. Redirect to Spotify auth page     │
       │ /api/auth/login?user_id=...         │
       ▼                                      │
┌──────────────────┐                         │
│  Spotify OAuth   │ 3. User authorizes app  │
│    Page          │◄────────────────────────┘
└─────┬────────────┘
      │ 4. Authorization code
      │
      ▼
┌──────────────────────────┐
│  Your API Backend        │ 5. Exchange code for Spotify token
│  /api/auth/callback      │
└──────┬───────────────────┘
       │
       │ 6. Create JWT with Spotify token
       │
       ▼
┌──────────────────────────┐
│  Client receives JWT     │ 7. JWT stored in browser/app
│  access_token            │
└──────┬───────────────────┘
       │
       │ 8. Include JWT in future requests
       │
       ▼
┌──────────────────────────┐
│  Protected Endpoints     │ 9. API uses Spotify token
│  /api/discover/...       │    to access Spotify API
└──────────────────────────┘
```

## Code Examples

### JavaScript (Frontend)

```javascript
// 1. Login
window.location.href = 'http://localhost:8000/api/auth/login?user_id=my_user_id';

// 2. After redirect, store token
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('access_token');
localStorage.setItem('jwt_token', token);

// 3. Use token in API calls
async function getRecommendations() {
  const token = localStorage.getItem('jwt_token');
  const response = await fetch(
    'http://localhost:8000/api/discover/recommendations?genres=rock',
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  return response.json();
}
```

### Python (Backend)

```python
import requests

# 1. Get JWT token (from OAuth callback)
response = requests.get('http://localhost:8000/api/auth/callback', 
                       params={'code': auth_code, 'state': state})
token = response.json()['access_token']

# 2. Use token
headers = {'Authorization': f'Bearer {token}'}
recs = requests.get(
    'http://localhost:8000/api/discover/recommendations',
    params={'genres': 'rock,pop'},
    headers=headers
)
print(recs.json())
```

## Files Added/Modified

**New Files:**
- `app/oauth.py` - OAuth 2.0 implementation
- `app/routes/auth_routes.py` - Authentication endpoints
- `OAUTH_SETUP.md` - Detailed setup guide

**Modified Files:**
- `app/main.py` - Added auth routes
- `app/auth.py` - Updated JWT verification
- `app/spotify_client.py` - Now uses user's OAuth token
- `app/routes/recommendations.py` - Updated for OAuth integration
- `requirements.txt` - Added dependencies

## Testing

All 30 tests pass ✅

```bash
python -m pytest tests/ -v
```

## Important Notes

⚠️ **Security Considerations:**

1. **Never expose Client Secret** in frontend code
2. **Use HTTPS in production** for all OAuth flows
3. **Store tokens securely** (HttpOnly cookies recommended)
4. **Implement token refresh** before expiration
5. **Validate all state parameters** to prevent CSRF

## Next Steps

1. Complete the Setup section above
2. Test the OAuth flow manually
3. Integrate into your frontend
4. Configure for production (HTTPS, secure token storage)
5. Implement token refresh mechanism

## Troubleshooting

**"Spotify Client ID not configured"**
- Ensure `SPOTIFY_CLIENT_ID` environment variable is set

**"Invalid redirect_uri"**
- Match the redirect URI in your Spotify app settings exactly

**"Failed to exchange code"**
- Verify `SPOTIFY_CLIENT_SECRET` is correct
- Check if code hasn't expired (10 minute validity)

**"Token expired"**
- Use refresh token to get new access token via `/api/auth/refresh`

## More Help

See `OAUTH_SETUP.md` for:
- Detailed setup instructions
- Complete API reference
- Advanced configuration
- Production deployment guide
- Additional code examples
