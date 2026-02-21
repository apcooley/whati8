"""Application-wide constants."""

# Nutrient IDs (from USDA FoodData Central / database)
# These are the standard IDs for key macronutrients
NUTRIENT_IDS = {
    "calories": 1008,  # Energy (kcal)
    "protein": 1003,   # Protein
    "carbs": 1005,     # Carbohydrate, by difference
    "fat": 1004,       # Total lipid (fat)
    "fiber": 1079,     # Fiber, total dietary
}

# Nutrient names (for looking up by name if ID isn't available)
NUTRIENT_NAMES = {
    "calories": "Energy",
    "protein": "Protein",
    "carbs": "Carbohydrate, by difference",
    "fat": "Total lipid (fat)",
    "fiber": "Fiber, total dietary",
}

# Food Search
FOOD_SEARCH_SIMILARITY_THRESHOLD = 0.1
FOOD_SEARCH_DEFAULT_LIMIT = 20
FOOD_SEARCH_MAX_LIMIT = 100

# AI
AI_MAX_TOKENS = 1024
AI_INPUT_MAX_LENGTH = 500
AI_MEAL_HINT_MAX_LENGTH = 50
AI_MAX_MATCHES_PER_ITEM = 20  # Return top 20, let LLM decide what matches
AI_MAX_MATCHES_LIMIT = 10
AI_HIGH_SIMILARITY_THRESHOLD = 0.8
AI_LOW_CONFIDENCE_THRESHOLD = 0.7

# Food Matching
FOOD_MATCH_SIMILARITY_THRESHOLD = 0.05  # Very permissive - let LLM filter bad matches

# Auth
PASSWORD_MIN_LENGTH = 8
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
JWT_MIN_SECRET_LENGTH = 32
JWT_MIN_UNIQUE_CHARS = 10

# Pagination
DEFAULT_PAGE_OFFSET = 0

# Food Logs
FOOD_LOG_DEFAULT_LIMIT = 50
FOOD_LOG_MAX_LIMIT = 200
FOOD_LOG_NOTES_MAX_LENGTH = 500

# Agent
AGENT_MAX_MESSAGE_LENGTH = 1000
AGENT_MAX_HISTORY_LENGTH = 20
AGENT_CONVERSATION_EXPIRATION_MINUTES = 60
AGENT_MAX_TOOL_CALLS_PER_MESSAGE = 5
