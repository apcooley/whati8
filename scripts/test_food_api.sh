#!/bin/bash
set -e

BASE_URL="http://localhost:8000"

echo "======================================================================"
echo "Testing Food Search API"
echo "======================================================================"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Register a test user (or skip if exists)
echo -e "\n${BLUE}1. Registering test user...${NC}"
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "foodtester",
    "email": "foodtester@example.com",
    "password": "password123"
  }' || echo '{"detail":"User already exists"}')
echo "$REGISTER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "User may already exist"

# 2. Login to get token
echo -e "\n${BLUE}2. Logging in...${NC}"
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "login": "foodtester",
    "password": "password123"
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
  echo "Failed to get auth token!"
  exit 1
fi
echo -e "${GREEN}✓ Got authentication token${NC}"

# 3. Test food search - exact match
echo -e "\n${BLUE}3. Testing food search: 'chicken'${NC}"
curl -s "$BASE_URL/foods/search?q=chicken&limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4. Test food search - fuzzy match (typo)
echo -e "\n${BLUE}4. Testing fuzzy search: 'chiken' (typo)${NC}"
curl -s "$BASE_URL/foods/search?q=chiken&limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 5. Test food search - another example
echo -e "\n${BLUE}5. Testing search: 'brocoli' (typo)${NC}"
curl -s "$BASE_URL/foods/search?q=brocoli&limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 6. Get a specific food ID from search and fetch details
echo -e "\n${BLUE}6. Getting food details for first search result...${NC}"
FOOD_ID=$(curl -s "$BASE_URL/foods/search?q=chicken&limit=1" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys, json; print(json.load(sys.stdin)['results'][0]['id'])")

echo -e "${BLUE}Fetching details for food ID: $FOOD_ID${NC}"
curl -s "$BASE_URL/foods/$FOOD_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -50

# 7. Test without authentication (should fail)
echo -e "\n${BLUE}7. Testing without authentication (should fail)...${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/foods/search?q=chicken")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
if [ "$HTTP_CODE" = "401" ]; then
  echo -e "${GREEN}✓ Correctly rejected unauthenticated request${NC}"
else
  echo "Expected 401, got $HTTP_CODE"
fi

echo -e "\n======================================================================"
echo -e "${GREEN}✓ Food Search API Tests Complete!${NC}"
echo "======================================================================"
echo ""
echo "Try it in Swagger UI: http://localhost:8000/docs"
echo ""
