#!/usr/bin/env python
"""
Complete OAuth 2.0 Flow Example - Music Discovery API

This example demonstrates the complete OAuth flow for authenticating with Spotify
and getting personalized music recommendations.
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import json
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8000"
USER_ID = "demo_user_123"

# This will store the token when the callback is received
received_token = None
received_code = None
received_state = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""
    
    def do_GET(self):
        global received_token, received_code, received_state
        
        # Parse the URL and query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Extract code and state from callback
        code = query_params.get('code', [None])[0]
        state = query_params.get('state', [None])[0]
        error = query_params.get('error', [None])[0]
        
        if error:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<h1>Authorization Error</h1><p>{error}</p>".encode())
            return
        
        if not code:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Missing Authorization Code</h1>")
            return
        
        # Store the code and state
        received_code = code
        received_state = state
        
        # Send success response to browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <html>
        <head><title>OAuth Success</title></head>
        <body>
        <h1>✓ Authorization Successful!</h1>
        <p>You can close this window and return to your terminal.</p>
        <p>Your API token will be ready to use.</p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def start_callback_server(port=8080):
    """Start a simple HTTP server to receive OAuth callback"""
    server = HTTPServer(('localhost', port), OAuthCallbackHandler)
    print(f"Callback server listening on http://localhost:{port}")
    server.timeout = 30  # Wait 30 seconds for callback
    server.handle_request()
    server.server_close()


def step_1_initiate_login():
    """Step 1: Initiate Spotify OAuth login"""
    print("\n" + "="*60)
    print("STEP 1: Initiating Spotify OAuth Login")
    print("="*60)
    
    # Construct login URL
    login_url = f"{API_BASE_URL}/api/auth/login?user_id={USER_ID}"
    
    print(f"\nOpening Spotify login page...")
    print(f"Login URL: {login_url}")
    
    # Open in browser
    webbrowser.open(login_url)
    
    # Start callback server to receive redirect
    print("\nWaiting for Spotify authorization...")
    print("(Please authorize the app in your browser)")
    start_callback_server()
    
    return received_code, received_state


def step_2_exchange_code_for_token(code: str, state: str) -> Optional[str]:
    """Step 2: Exchange authorization code for JWT token"""
    print("\n" + "="*60)
    print("STEP 2: Exchanging Authorization Code for Token")
    print("="*60)
    
    print(f"\nCode received: {code[:20]}...")
    print(f"State: {state}")
    
    # Call the callback endpoint
    callback_url = f"{API_BASE_URL}/api/auth/callback"
    params = {'code': code, 'state': state}
    
    try:
        response = requests.get(callback_url, params=params)
        response.raise_for_status()
        
        token_data = response.json()
        jwt_token = token_data.get('access_token')
        
        if jwt_token:
            print(f"\n✓ Token acquired successfully!")
            print(f"Token (first 50 chars): {jwt_token[:50]}...")
            print(f"Token type: {token_data.get('token_type')}")
            print(f"Expires in: {token_data.get('expires_in')} seconds")
            
            return jwt_token
        else:
            print(f"✗ Error: No token in response")
            print(f"Response: {token_data}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error exchanging code: {e}")
        return None


def step_3_get_user_profile(token: str):
    """Step 3: Get current user's Spotify profile"""
    print("\n" + "="*60)
    print("STEP 3: Getting User Profile")
    print("="*60)
    
    headers = {'Authorization': f'Bearer {token}'}
    params = {'authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/auth/me",
            params=params,
            headers=headers
        )
        response.raise_for_status()
        
        profile = response.json()
        
        print(f"\n✓ User Profile Retrieved:")
        print(f"  Spotify ID: {profile.get('id')}")
        print(f"  Display Name: {profile.get('display_name')}")
        print(f"  Email: {profile.get('email')}")
        print(f"  Followers: {profile.get('followers', {}).get('total', 0)}")
        print(f"  Profile URI: {profile.get('uri')}")
        
        return profile
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error getting profile: {e}")
        return None


def step_4_get_recommendations(token: str):
    """Step 4: Get personalized music recommendations"""
    print("\n" + "="*60)
    print("STEP 4: Getting Music Recommendations")
    print("="*60)
    
    # Ask user for genres
    print("\nEnter genres to filter by (comma-separated, e.g., rock,pop,jazz)")
    genres = input("Genres: ").strip() or "rock,pop"
    
    print(f"Requesting recommendations for: {genres}")
    
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'genres': genres,
        'min_popularity': 50,
        'limit': 20
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/discover/recommendations",
            params=params,
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        tracks = data.get('recommendedTracks', [])
        
        if tracks:
            print(f"\n✓ Got {len(tracks)} recommendations!")
            print("\nTop 5 Tracks:")
            for i, track in enumerate(tracks[:5], 1):
                print(f"\n{i}. {track.get('title')}")
                print(f"   Artist: {track.get('artist')}")
                print(f"   Genres: {', '.join(track.get('genres', []))}")
                print(f"   Popularity: {track.get('popularity')}/100")
                print(f"   Released: {track.get('album', {}).get('release_date')}")
        else:
            print("\n✗ No recommendations found")
            
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error getting recommendations: {e}")
        return None


def main():
    """Run the complete OAuth flow"""
    print("\n" + "="*60)
    print("Music Discovery API - OAuth 2.0 Flow Demo")
    print("="*60)
    
    print("\nMake sure:")
    print("1. Server is running: python -m uvicorn app.main:app --reload")
    print("2. Environment variables are set (SPOTIFY_CLIENT_ID, etc.)")
    print("3. Spotify app redirect URI is: http://localhost:8000/api/auth/callback")
    
    input("\nPress Enter to start...")
    
    # Step 1: Initiate login
    code, state = step_1_initiate_login()
    if not code:
        print("✗ Failed to get authorization code")
        return
    
    # Step 2: Exchange code for token
    token = step_2_exchange_code_for_token(code, state)
    if not token:
        print("✗ Failed to get token")
        return
    
    # Step 3: Get user profile
    profile = step_3_get_user_profile(token)
    
    # Step 4: Get recommendations
    recs = step_4_get_recommendations(token)
    
    print("\n" + "="*60)
    print("✓ OAuth Flow Complete!")
    print("="*60)
    print(f"\nYour JWT Token:")
    print(f"{token}\n")
    print("Use this token in the Authorization header for API requests:")
    print(f'curl -H "Authorization: Bearer {token}" \\')
    print(f'  "{API_BASE_URL}/api/discover/recommendations?genres=rock"')


if __name__ == "__main__":
    main()
