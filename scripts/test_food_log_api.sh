#!/bin/bash
# Test script for Food Log CRUD API
set -e

BASE_URL="http://localhost:8000"
CONTENT_TYPE="Content-Type: application/json"

echo "========================================="
echo "Food Log API Test Suite"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function for test results
test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        exit 1
    fi
}

# Helper function for expected failures
expect_fail() {
    if [ $1 -ne 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2 (expected failure)"
    else
        echo -e "${RED}✗ FAIL${NC}: $2 (should have failed but didn't)"
        exit 1
    fi
}

echo "1. Login to get authentication token..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "$CONTENT_TYPE" \
    -d '{
        "login": "foodlog_testuser",
        "password": "testpass123"
    }')

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗ FAIL${NC}: Could not obtain authentication token"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

test_result 0 "Login successful"
echo ""

# Authorization header
AUTH="Authorization: Bearer $TOKEN"

echo "2. Create a food log entry..."
CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/logs" \
    -H "$CONTENT_TYPE" \
    -H "$AUTH" \
    -d '{
        "food_id": 102,
        "meal_id": 1,
        "quantity": 1.5,
        "logged_at": "2026-02-07T08:30:00",
        "notes": "Breakfast broccoli"
    }')

LOG_ID=$(echo $CREATE_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ -z "$LOG_ID" ]; then
    echo -e "${RED}✗ FAIL${NC}: Could not create food log"
    echo "Response: $CREATE_RESPONSE"
    exit 1
fi

test_result 0 "Created food log with ID: $LOG_ID"
echo "Response:"
echo "$CREATE_RESPONSE" | python3 -m json.tool
echo ""

echo "3. Get the food log by ID..."
GET_RESPONSE=$(curl -s "$BASE_URL/logs/$LOG_ID" \
    -H "$AUTH")

RETRIEVED_ID=$(echo $GET_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)

if [ "$RETRIEVED_ID" != "$LOG_ID" ]; then
    echo -e "${RED}✗ FAIL${NC}: Retrieved log ID doesn't match"
    exit 1
fi

test_result 0 "Retrieved food log successfully"
echo "Food name: $(echo $GET_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['food']['name'])")"
echo "Meal name: $(echo $GET_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['meal']['name'])")"
echo ""

echo "4. List all food logs..."
LIST_RESPONSE=$(curl -s "$BASE_URL/logs?limit=10" \
    -H "$AUTH")

TOTAL=$(echo $LIST_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null)

if [ -z "$TOTAL" ]; then
    echo -e "${RED}✗ FAIL${NC}: Could not list food logs"
    exit 1
fi

test_result 0 "Listed food logs (total: $TOTAL)"
echo ""

echo "5. Filter by date..."
DATE_FILTER_RESPONSE=$(curl -s "$BASE_URL/logs?date=2026-02-07" \
    -H "$AUTH")

DATE_TOTAL=$(echo $DATE_FILTER_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null)

if [ -z "$DATE_TOTAL" ]; then
    echo -e "${RED}✗ FAIL${NC}: Could not filter by date"
    exit 1
fi

test_result 0 "Filtered by date (found: $DATE_TOTAL logs)"
echo ""

echo "6. Filter by meal..."
MEAL_FILTER_RESPONSE=$(curl -s "$BASE_URL/logs?meal_id=1" \
    -H "$AUTH")

MEAL_TOTAL=$(echo $MEAL_FILTER_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null)

if [ -z "$MEAL_TOTAL" ]; then
    echo -e "${RED}✗ FAIL${NC}: Could not filter by meal"
    exit 1
fi

test_result 0 "Filtered by meal (found: $MEAL_TOTAL logs)"
echo ""

echo "7. Update the food log..."
UPDATE_RESPONSE=$(curl -s -X PUT "$BASE_URL/logs/$LOG_ID" \
    -H "$CONTENT_TYPE" \
    -H "$AUTH" \
    -d '{
        "quantity": 2.0,
        "notes": "Updated: more broccoli"
    }')

UPDATED_QUANTITY=$(echo $UPDATE_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['quantity'])" 2>/dev/null)

if [ "$UPDATED_QUANTITY" != "2.0" ]; then
    echo -e "${RED}✗ FAIL${NC}: Quantity not updated correctly"
    exit 1
fi

test_result 0 "Updated food log (new quantity: $UPDATED_QUANTITY)"
echo ""

echo "8. Test validation - create with invalid food_id..."
INVALID_CREATE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/logs" \
    -H "$CONTENT_TYPE" \
    -H "$AUTH" \
    -d '{
        "food_id": 999999,
        "quantity": 1.0,
        "logged_at": "2026-02-07T08:30:00"
    }')

HTTP_CODE=$(echo "$INVALID_CREATE" | tail -n1)

if [ "$HTTP_CODE" = "404" ]; then
    test_result 0 "Validation: Invalid food_id rejected (404)"
else
    echo -e "${RED}✗ FAIL${NC}: Should have received 404 for invalid food_id, got $HTTP_CODE"
    exit 1
fi
echo ""

echo "9. Test validation - create with negative quantity..."
NEGATIVE_QTY=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/logs" \
    -H "$CONTENT_TYPE" \
    -H "$AUTH" \
    -d '{
        "food_id": 102,
        "quantity": -1.0,
        "logged_at": "2026-02-07T08:30:00"
    }')

HTTP_CODE=$(echo "$NEGATIVE_QTY" | tail -n1)

if [ "$HTTP_CODE" = "422" ]; then
    test_result 0 "Validation: Negative quantity rejected (422)"
else
    echo -e "${RED}✗ FAIL${NC}: Should have received 422 for negative quantity, got $HTTP_CODE"
    exit 1
fi
echo ""

echo "10. Test authorization - create second user..."
# Register second user if not exists
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
    -H "$CONTENT_TYPE" \
    -d '{
        "username": "testuser2",
        "email": "testuser2@example.com",
        "password": "password123"
    }' 2>/dev/null || true)

# Login as second user
LOGIN2_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "$CONTENT_TYPE" \
    -d '{
        "login": "testuser2",
        "password": "password123"
    }')

TOKEN2=$(echo $LOGIN2_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ ! -z "$TOKEN2" ]; then
    echo "11. Test authorization - second user tries to access first user's log..."
    AUTH2="Authorization: Bearer $TOKEN2"

    UNAUTHORIZED_GET=$(curl -s -w "\n%{http_code}" "$BASE_URL/logs/$LOG_ID" \
        -H "$AUTH2")

    HTTP_CODE=$(echo "$UNAUTHORIZED_GET" | tail -n1)

    if [ "$HTTP_CODE" = "404" ]; then
        test_result 0 "Authorization: User cannot access other user's logs (404)"
    else
        echo -e "${RED}✗ FAIL${NC}: Should have received 404 for unauthorized access, got $HTTP_CODE"
        exit 1
    fi
    echo ""
else
    echo -e "${YELLOW}⚠ SKIP${NC}: Could not create second user for authorization test"
    echo ""
fi

echo "12. Delete the food log..."
DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE_URL/logs/$LOG_ID" \
    -H "$AUTH")

HTTP_CODE=$(echo "$DELETE_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "204" ]; then
    test_result 0 "Deleted food log (204 No Content)"
else
    echo -e "${RED}✗ FAIL${NC}: Delete failed with code $HTTP_CODE"
    exit 1
fi
echo ""

echo "13. Verify deletion - try to get deleted log..."
VERIFY_DELETE=$(curl -s -w "\n%{http_code}" "$BASE_URL/logs/$LOG_ID" \
    -H "$AUTH")

HTTP_CODE=$(echo "$VERIFY_DELETE" | tail -n1)

if [ "$HTTP_CODE" = "404" ]; then
    test_result 0 "Verification: Deleted log not found (404)"
else
    echo -e "${RED}✗ FAIL${NC}: Deleted log should return 404, got $HTTP_CODE"
    exit 1
fi
echo ""

echo "========================================="
echo -e "${GREEN}✓ All tests passed!${NC}"
echo "========================================="
