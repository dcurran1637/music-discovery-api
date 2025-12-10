#!/usr/bin/env python3
"""
Deployment Verification - Python Version
Tests deployed API endpoints and verifies authentication protection
Usage: python scripts/verify_deployment.py <BASE_URL>
Example: python scripts/verify_deployment.py https://music-discovery-api.onrender.com
"""

import sys
import requests
import json
from typing import Tuple
from datetime import datetime

# ANSI color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class DeploymentVerifier:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def print_header(self, text: str):
        print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BLUE}{text}{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}\n")
        
    def test_endpoint(self, name: str, endpoint: str, expected_status: int, 
                     method: str = 'GET', headers: dict = None) -> bool:
        """Test an endpoint and verify status code"""
        print(f"{Colors.YELLOW}Testing: {name}{Colors.NC}")
        url = f"{self.base_url}{endpoint}"
        print(f"  URL: {url}")
        print(f"  Expected: HTTP {expected_status}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
            elif method == 'POST':
                response = requests.post(url, headers=headers, timeout=10, allow_redirects=False)
            elif method == 'OPTIONS':
                response = requests.options(url, headers=headers, timeout=10)
            else:
                response = requests.request(method, url, headers=headers, timeout=10, allow_redirects=False)
                
            status = response.status_code
            
            if status == expected_status:
                print(f"  {Colors.GREEN}✅ PASSED{Colors.NC} (HTTP {status})")
                self.passed += 1
                return True
            else:
                print(f"  {Colors.RED}❌ FAILED{Colors.NC} (Expected {expected_status}, got {status})")
                if response.text:
                    try:
                        print(f"  Response: {json.dumps(response.json(), indent=2)[:200]}")
                    except:
                        print(f"  Response: {response.text[:200]}")
                self.failed += 1
                return False
                
        except requests.exceptions.Timeout:
            print(f"  {Colors.RED}❌ FAILED{Colors.NC} - Request timeout")
            self.failed += 1
            return False
        except requests.exceptions.ConnectionError:
            print(f"  {Colors.RED}❌ FAILED{Colors.NC} - Connection error")
            self.failed += 1
            return False
        except Exception as e:
            print(f"  {Colors.RED}❌ FAILED{Colors.NC} - {str(e)}")
            self.failed += 1
            return False
        finally:
            print()
    
    def check_json_response(self, endpoint: str) -> bool:
        """Check if endpoint returns valid JSON"""
        print(f"{Colors.YELLOW}Checking JSON response format...{Colors.NC}")
        try:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
            data = response.json()
            print(f"{Colors.GREEN}✅ PASSED{Colors.NC} - Valid JSON response")
            self.passed += 1
            return True
        except json.JSONDecodeError:
            print(f"{Colors.RED}❌ FAILED{Colors.NC} - Invalid JSON response")
            self.failed += 1
            return False
        except Exception as e:
            print(f"{Colors.RED}❌ FAILED{Colors.NC} - {str(e)}")
            self.failed += 1
            return False
        finally:
            print()
    
    def check_response_time(self, endpoint: str, threshold: float = 2.0) -> bool:
        """Check endpoint response time"""
        print(f"{Colors.YELLOW}Testing response time...{Colors.NC}")
        try:
            start = datetime.now()
            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
            duration = (datetime.now() - start).total_seconds()
            
            print(f"  Response time: {duration:.3f}s")
            if duration < threshold:
                print(f"  {Colors.GREEN}✅ PASSED{Colors.NC} - Response under {threshold} seconds")
                self.passed += 1
                return True
            else:
                print(f"  {Colors.YELLOW}⚠️ SLOW{Colors.NC} - Response over {threshold} seconds")
                self.warnings += 1
                return False
        except Exception as e:
            print(f"  {Colors.RED}❌ FAILED{Colors.NC} - {str(e)}")
            self.failed += 1
            return False
        finally:
            print()
    
    def run_all_tests(self):
        """Run complete test suite"""
        self.print_header(f"Deployment Verification for: {self.base_url}")
        
        # Public endpoints
        self.print_header("Public Endpoints")
        self.test_endpoint("Root Endpoint", "/", 200)
        self.test_endpoint("Health Check (Live)", "/api/health/live", 200)
        self.test_endpoint("Health Check (Ready)", "/api/health/ready", 200)
        self.test_endpoint("API Documentation", "/docs", 200)
        self.test_endpoint("OpenAPI Schema", "/openapi.json", 200)
        
        # Authentication endpoints
        self.print_header("Authentication Endpoints")
        self.test_endpoint("OAuth Login", "/api/auth/login", 307)
        
        # Protected endpoints (should require auth)
        self.print_header("Protected Endpoints (Without Auth)")
        self.test_endpoint("My Playlists (No Auth)", "/api/playlists/me", 401)
        self.test_endpoint("Create Playlist (No Auth)", "/api/playlists", 401, method='POST')
        self.test_endpoint("Recommendations (No Auth)", "/api/recommendations/track-based", 401)
        self.test_endpoint("My Top Tracks (No Auth)", "/api/tracks/top", 401)
        self.test_endpoint("My Top Artists (No Auth)", "/api/artists/top", 401)
        
        # Response format
        self.print_header("API Response Format")
        self.check_json_response("/api/health/live")
        
        # Performance
        self.print_header("Performance Check")
        self.check_response_time("/api/health/live")
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("Verification Summary")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.NC}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.NC}")
        if self.warnings > 0:
            print(f"{Colors.YELLOW}Warnings: {self.warnings}{Colors.NC}")
        print()
        
        if self.failed == 0:
            print(f"{Colors.GREEN}🎉 All tests passed!{Colors.NC}\n")
            print("✅ Deployment verification successful")
            print("✅ Public endpoints accessible")
            print("✅ Protected endpoints require authentication")
            print("✅ Health checks responding\n")
            print("Next steps:")
            print(f"1. Test OAuth flow: {self.base_url}/api/auth/login")
            print(f"2. View API docs: {self.base_url}/docs")
            print("3. Monitor logs in Render dashboard")
            return 0
        else:
            print(f"{Colors.RED}❌ Some tests failed{Colors.NC}\n")
            print("Please check:")
            print("1. Service is fully deployed and running")
            print("2. Environment variables are set correctly")
            print("3. Database and Redis connections are working")
            print("4. Check logs: Render Dashboard → Logs")
            return 1

def main():
    if len(sys.argv) != 2:
        print(f"{Colors.RED}Error: Please provide base URL{Colors.NC}")
        print(f"Usage: {sys.argv[0]} <BASE_URL>")
        print(f"Example: {sys.argv[0]} https://music-discovery-api.onrender.com")
        sys.exit(1)
    
    base_url = sys.argv[1]
    verifier = DeploymentVerifier(base_url)
    exit_code = verifier.run_all_tests()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
