#!/bin/bash
# Test script for AI-powered food resolution endpoint

set -e

API_URL="http://localhost:8000"
TOKEN=""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== whati8 Food Resolver API Test ==="
echo ""

# Step 1: Login to get token
echo "Step 1: Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo -e "${RED}❌ Login failed. Make sure testuser exists.${NC}"
  echo "Create user with: uv run python -m whati8 auth register"
  exit 1
fi

echo -e "${GREEN}✓ Logged in successfully${NC}"
echo ""

# Test Case 1: Simple breakfast input
echo "Test Case 1: Simple breakfast input"
echo "Input: 'I had 2 eggs and toast for breakfast'"
echo ""
RESPONSE=$(curl -s -X POST "$API_URL/foods/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I had 2 eggs and toast for breakfast",
    "max_matches_per_item": 3
  }')

echo "$RESPONSE" | python3 -m json.tool
echo ""
echo "Expected:"
echo "  - 2 resolved items (eggs, toast)"
echo "  - Meal context: Breakfast"
echo "  - Confidence scores > 0.7"
echo ""
read -p "Press Enter to continue..."
echo ""

# Test Case 2: Measured dinner
echo "Test Case 2: Measured dinner"
echo "Input: '8oz chicken breast with broccoli'"
echo ""
RESPONSE=$(curl -s -X POST "$API_URL/foods/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "8oz chicken breast with broccoli",
    "max_matches_per_item": 3
  }')

echo "$RESPONSE" | python3 -m json.tool
echo ""
echo "Expected:"
echo "  - Quantity: 8, Unit: oz for chicken"
echo "  - Both items matched in database"
echo ""
read -p "Press Enter to continue..."
echo ""

# Test Case 3: Ambiguous input
echo "Test Case 3: Ambiguous input (vague quantities)"
echo "Input: 'had some chicken and rice'"
echo ""
RESPONSE=$(curl -s -X POST "$API_URL/foods/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "had some chicken and rice",
    "max_matches_per_item": 3
  }')

echo "$RESPONSE" | python3 -m json.tool
echo ""
echo "Expected:"
echo "  - Lower confidence scores (<0.7)"
echo "  - Multiple matches for ambiguous foods"
echo ""
read -p "Press Enter to continue..."
echo ""

# Test Case 4: With meal hint
echo "Test Case 4: Using meal hint"
echo "Input: 'grilled salmon and asparagus' with meal_hint='dinner'"
echo ""
RESPONSE=$(curl -s -X POST "$API_URL/foods/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "grilled salmon and asparagus",
    "meal_hint": "dinner",
    "max_matches_per_item": 3
  }')

echo "$RESPONSE" | python3 -m json.tool
echo ""
echo "Expected:"
echo "  - Meal context: Dinner"
echo "  - Preparation method included (grilled)"
echo ""
read -p "Press Enter to continue..."
echo ""

# Test Case 5: Invalid input (too vague)
echo "Test Case 5: Error handling - invalid input"
echo "Input: 'xyz'"
echo ""
RESPONSE=$(curl -s -X POST "$API_URL/foods/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "xyz",
    "max_matches_per_item": 3
  }')

echo "$RESPONSE" | python3 -m json.tool
echo ""
echo "Expected:"
echo "  - 400 Bad Request"
echo "  - Error message about vague input"
echo ""

echo ""
echo -e "${GREEN}=== All test cases completed ===${NC}"
echo ""
echo "Notes:"
echo "  - AI parsing quality depends on Anthropic API key"
echo "  - Database matches depend on USDA data import"
echo "  - Check Swagger UI at: http://localhost:8000/docs"
