#!/bin/bash
# Test script for agent API endpoints

set -e

API_URL="${API_URL:-http://localhost:15853}"

echo "=== Testing Agent API ==="
echo

# 1. Login to get token
echo "1. Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"login":"foodlog_testuser","password":"testpass123"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to get auth token"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

echo "✓ Logged in successfully"
echo

# 2. Test agent chat endpoint
echo "2. Testing chat endpoint with simple message..."
CHAT_RESPONSE=$(curl -s -X POST "${API_URL}/agent/chat" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, I want to track my food",
    "session_id": "test-session-123"
  }')

echo "Response:"
echo "$CHAT_RESPONSE" | python3 -m json.tool
echo

# 3. Test with food logging query
echo "3. Testing food logging query..."
CHAT_RESPONSE2=$(curl -s -X POST "${API_URL}/agent/chat" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I had 2 eggs for breakfast",
    "session_id": "test-session-456"
  }')

echo "Response:"
echo "$CHAT_RESPONSE2" | python3 -m json.tool
echo

# 4. Test food search query
echo "4. Testing food search query..."
CHAT_RESPONSE3=$(curl -s -X POST "${API_URL}/agent/chat" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you find chicken in the database?",
    "session_id": "test-session-789"
  }')

echo "Response:"
echo "$CHAT_RESPONSE3" | python3 -m json.tool
echo

echo "=== All tests completed ==="
