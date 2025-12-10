#!/bin/bash

# ==============================================================================
# Deployment Verification Script
# ==============================================================================
# Tests deployed API endpoints and verifies authentication protection
# Usage: ./scripts/verify_deployment.sh <BASE_URL>
# Example: ./scripts/verify_deployment.sh https://music-discovery-api.onrender.com
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if URL provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide base URL${NC}"
    echo "Usage: $0 <BASE_URL>"
    echo "Example: $0 https://music-discovery-api.onrender.com"
    exit 1
fi

BASE_URL=$1
PASSED=0
FAILED=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Verification for: $BASE_URL${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test function
test_endpoint() {
    local name=$1
    local endpoint=$2
    local expected_status=$3
    local description=$4
    
    echo -e "${YELLOW}Testing: $name${NC}"
    echo "  URL: $BASE_URL$endpoint"
    echo "  Expected: HTTP $expected_status"
    
    # Make request and capture status code
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint" 2>/dev/null || echo "000")
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "  ${GREEN}✅ PASSED${NC} (HTTP $status_code)"
        ((PASSED++))
    else
        echo -e "  ${RED}❌ FAILED${NC} (Expected $expected_status, got $status_code)"
        echo "  Response: $body"
        ((FAILED++))
    fi
    echo ""
}

# Test with auth header
test_protected_endpoint() {
    local name=$1
    local endpoint=$2
    local token=$3
    local expected_status=$4
    
    echo -e "${YELLOW}Testing: $name${NC}"
    echo "  URL: $BASE_URL$endpoint"
    echo "  Auth: Bearer token"
    echo "  Expected: HTTP $expected_status"
    
    if [ -z "$token" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint" 2>/dev/null || echo "000")
    else
        response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $token" "$BASE_URL$endpoint" 2>/dev/null || echo "000")
    fi
    
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "  ${GREEN}✅ PASSED${NC} (HTTP $status_code)"
        ((PASSED++))
    else
        echo -e "  ${RED}❌ FAILED${NC} (Expected $expected_status, got $status_code)"
        echo "  Response: $body"
        ((FAILED++))
    fi
    echo ""
}

echo -e "${BLUE}=== Public Endpoints ===${NC}"
echo ""

# Test root endpoint
test_endpoint "Root Endpoint" "/" "200" "Should return API info"

# Test health endpoints
test_endpoint "Health Check (Live)" "/api/health/live" "200" "Liveness probe"
test_endpoint "Health Check (Ready)" "/api/health/ready" "200" "Readiness probe"

# Test API documentation
test_endpoint "API Documentation" "/docs" "200" "OpenAPI docs"
test_endpoint "OpenAPI Schema" "/openapi.json" "200" "OpenAPI spec"

echo -e "${BLUE}=== Authentication Endpoints ===${NC}"
echo ""

# Test OAuth endpoints
test_endpoint "OAuth Login" "/api/auth/login" "307" "Should redirect to Spotify"

echo -e "${BLUE}=== Protected Endpoints (Without Auth) ===${NC}"
echo ""

# These should all require authentication
test_protected_endpoint "My Playlists (No Auth)" "/api/playlists/me" "" "401"
test_protected_endpoint "Create Playlist (No Auth)" "/api/playlists" "" "401"
test_protected_endpoint "Recommendations (No Auth)" "/api/recommendations/track-based" "" "401"
test_protected_endpoint "My Top Tracks (No Auth)" "/api/tracks/top" "" "401"
test_protected_endpoint "My Top Artists (No Auth)" "/api/artists/top" "" "401"

echo -e "${BLUE}=== API Response Format ===${NC}"
echo ""

# Check if responses are JSON
echo -e "${YELLOW}Checking response format...${NC}"
response=$(curl -s "$BASE_URL/api/health/live")
if echo "$response" | jq . > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASSED${NC} - Valid JSON response"
    ((PASSED++))
else
    echo -e "${RED}❌ FAILED${NC} - Invalid JSON response"
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}=== Security Headers ===${NC}"
echo ""

# Check for security headers
echo -e "${YELLOW}Checking security headers...${NC}"
headers=$(curl -s -I "$BASE_URL/")

check_header() {
    local header=$1
    if echo "$headers" | grep -qi "$header"; then
        echo -e "  ${GREEN}✅${NC} $header present"
        return 0
    else
        echo -e "  ${YELLOW}⚠️${NC} $header missing"
        return 1
    fi
}

check_header "content-type"

echo ""

echo -e "${BLUE}=== CORS Configuration ===${NC}"
echo ""

# Test CORS
echo -e "${YELLOW}Testing CORS headers...${NC}"
cors_response=$(curl -s -I -X OPTIONS "$BASE_URL/" -H "Origin: https://example.com" -H "Access-Control-Request-Method: GET")
if echo "$cors_response" | grep -qi "access-control"; then
    echo -e "${GREEN}✅ PASSED${NC} - CORS headers present"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️ INFO${NC} - CORS headers not found (may not be configured)"
fi
echo ""

echo -e "${BLUE}=== Performance Check ===${NC}"
echo ""

# Test response time
echo -e "${YELLOW}Testing response time...${NC}"
time_total=$(curl -s -o /dev/null -w "%{time_total}" "$BASE_URL/api/health/live")
echo "  Response time: ${time_total}s"
if (( $(echo "$time_total < 2.0" | bc -l) )); then
    echo -e "  ${GREEN}✅ PASSED${NC} - Response under 2 seconds"
    ((PASSED++))
else
    echo -e "  ${YELLOW}⚠️ SLOW${NC} - Response over 2 seconds (may be cold start)"
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    echo ""
    echo "✅ Deployment verification successful"
    echo "✅ Public endpoints accessible"
    echo "✅ Protected endpoints require authentication"
    echo "✅ Health checks responding"
    echo ""
    echo "Next steps:"
    echo "1. Test OAuth flow: $BASE_URL/api/auth/login"
    echo "2. View API docs: $BASE_URL/docs"
    echo "3. Monitor logs in Render dashboard"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    echo ""
    echo "Please check:"
    echo "1. Service is fully deployed and running"
    echo "2. Environment variables are set correctly"
    echo "3. Database and Redis connections are working"
    echo "4. Check logs: Render Dashboard → Logs"
    exit 1
fi
