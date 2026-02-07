#!/bin/bash
# Test script for whati8 REST API

set -e

API_URL="${API_URL:-http://localhost:8000}"
echo "Testing whati8 API at $API_URL"
echo "========================================"
echo

# Test 1: Health check
echo "✓ Testing health check..."
curl -s "$API_URL/health"
echo -e "\n"

# Test 2: Register new user
echo "✓ Testing user registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser'"$(date +%s)"'","email":"test'"$(date +%s)"'@example.com","password":"password123"}')
echo "$REGISTER_RESPONSE"
echo

# Test 3: Login
echo "✓ Testing login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"login":"testapi","password":"password123"}')
echo "$LOGIN_RESPONSE"
TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
echo

# Test 4: Get current user (protected endpoint)
echo "✓ Testing protected endpoint /auth/me..."
curl -s "$API_URL/auth/me" \
  -H "Authorization: Bearer $TOKEN"
echo -e "\n"

# Test 5: Invalid token
echo "✓ Testing invalid token (should return 401)..."
curl -s "$API_URL/auth/me" \
  -H "Authorization: Bearer invalid_token"
echo -e "\n"

# Test 6: Missing token
echo "✓ Testing missing token (should return 401)..."
curl -s "$API_URL/auth/me"
echo -e "\n"

# Test 7: Duplicate registration
echo "✓ Testing duplicate registration (should return 409)..."
curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testapi","email":"testapi@example.com","password":"password123"}'
echo -e "\n"

# Test 8: Wrong password
echo "✓ Testing wrong password (should return 401)..."
curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"login":"testapi","password":"wrongpassword"}'
echo -e "\n"

# Test 9: Validation error
echo "✓ Testing validation error - short password (should return 422)..."
curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"test2","email":"test2@example.com","password":"short"}'
echo -e "\n"

echo "========================================"
echo "All tests completed!"
echo
echo "To test from LAN devices:"
echo "  export API_URL=http://192.168.1.11:8000"
echo "  ./scripts/test_api.sh"
