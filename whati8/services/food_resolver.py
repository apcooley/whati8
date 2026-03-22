"""Service for AI-powered natural language food resolution."""

import re as _re

from anthropic import Anthropic
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.config import settings
from whati8.constants import (
    AI_HIGH_SIMILARITY_THRESHOLD,
    AI_INPUT_MAX_LENGTH,
    AI_LOW_CONFIDENCE_THRESHOLD,
    AI_MAX_MATCHES_PER_ITEM,
    AI_MAX_TOKENS,
    AI_MEAL_HINT_MAX_LENGTH,
    FOOD_MATCH_SIMILARITY_THRESHOLD,
)
from whati8.logging_config import get_logger
from whati8.models.food import Food
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.food_portion import FoodPortion
from whati8.models.meal import Meal
from whati8.schemas.food_resolver import (
    FoodMatchOption,
    MealContext,
    ParsedFoodItem,
    PortionOption,
    ResolvedFoodItem,
    FoodResolveResponse,
)
from whati8.schemas.multi_food import (
    MultiFoodConfirmationItem,
    MultiFoodConfirmationResponse,
)
from whati8.services.embedding_service import (
    EmbeddingProvider,
    embed_query,
)

logger = get_logger(__name__)

# Hybrid search weights
KEYWORD_WEIGHT = 0.5
SEMANTIC_WEIGHT = 0.5
# Bonus for token-level signals (added on top of keyword score)
TOKEN_EXACT_BONUS = 0.3
TOKEN_STARTS_WITH_BONUS = 0.15
TOKEN_WORD_BONUS = 0.1
LENGTH_PENALTY_FACTOR = 0.002  # Per character


class FoodResolverService:
    """Service for resolving natural language food descriptions using AI."""

    # System prompt for Claude to extract food items
    SYSTEM_PROMPT = """You are a food parsing assistant for a nutrition tracking app. Your job is to extract structured food information from natural language.

Guidelines:
- Standardize food names (e.g., "eggs" → "egg", "chicken breasts" → "chicken breast")
- Convert word quantities to numbers ("two" → 2, "a few" → 3)
- Standardize units: oz, g, kg, lb, cup, tbsp, tsp, ml, pieces, slices, serving
- Include preparation methods if mentioned ("scrambled eggs", "grilled chicken")
- Set confidence based on clarity:
  - 0.9-1.0: Clear quantity and food ("2 eggs", "8oz chicken")
  - 0.7-0.89: Clear food, vague quantity ("some chicken", "a bowl of rice")
  - 0.5-0.69: Ambiguous food or quantity ("had a snack")
  - <0.5: Very unclear
- If a meal is mentioned (breakfast, lunch, dinner, snack), note it
- For items without explicit quantities, estimate reasonably (confidence <0.8)

IMPORTANT - Generate search_terms for each item:
- Include 2-5 alternative ways to search for the food in a database
- Start with the exact food_name, then add simpler/broader terms
- Examples:
  - "overnight oats" → ["overnight oats", "oats", "oatmeal", "rolled oats", "oat cereal", "cereal oat"]
  - "scrambled eggs" → ["scrambled eggs", "eggs scrambled", "egg"]
  - "grilled chicken breast" → ["grilled chicken breast", "chicken breast", "chicken"]
  - "2% milk" → ["2% milk", "milk 2%", "milk reduced fat", "milk"]
  - "toast" → ["toast", "bread", "wheat bread"]
  - "cereal" → ["cereal", "dry cereal", "breakfast cereal"]
- Try 3-5 variations: exact name, simpler names, common alternatives, component names
- This helps match foods in the USDA database which uses specific naming conventions

Extract all food items from the input text."""

    @staticmethod
    def _sanitize_input(text: str, max_length: int = 500) -> str:
        """
        Sanitize user input for AI prompt to prevent injection attacks.

        Args:
            text: User input to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text

        Raises:
            ValueError: If input is invalid or contains suspicious patterns
        """
        import re

        # Strip whitespace
        text = text.strip()

        # Validate length
        if len(text) < 1:
            raise ValueError("Input text cannot be empty")
        if len(text) > max_length:
            raise ValueError(f"Input text too long (max {max_length} characters)")

        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)

        # Check for prompt injection patterns
        suspicious_patterns = [
            r"ignore\s+(previous|above|all|prior|system)",
            r"system\s*:",
            r"<\|im_start\|>",
            r"<\|im_end\|>",
            r"<\|assistant\|>",
            r"###\s*Instruction",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                raise ValueError("Input contains suspicious patterns")

        return text

    @staticmethod
    async def parse_food_text(
        text: str, meal_hint: str | None = None
    ) -> tuple[list[ParsedFoodItem], str | None]:
        """
        Parse natural language food text using Claude AI with tool calling.

        Args:
            text: Natural language food description
            meal_hint: Optional meal context hint

        Returns:
            Tuple of (parsed food items, detected meal name)

        Raises:
            ValueError: If parsing fails or input is too vague
            anthropic.APIError: If AI service fails
        """
        import asyncio

        # Sanitize inputs to prevent prompt injection
        text = FoodResolverService._sanitize_input(text, max_length=AI_INPUT_MAX_LENGTH)
        if meal_hint:
            meal_hint = FoodResolverService._sanitize_input(
                meal_hint, max_length=AI_MEAL_HINT_MAX_LENGTH
            )

        logger.info(f"Parsing food text: '{text[:50]}...' (meal_hint: {meal_hint})")

        # Validate API key is configured
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured. "
                "Set environment variable to use food resolution. "
                "Get API key from https://console.anthropic.com/"
            )

        client = Anthropic(api_key=settings.anthropic_api_key)

        # Define tool schema for structured extraction
        tools = [
            {
                "name": "extract_food_items",
                "description": "Extract structured food items from natural language input",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "food_name": {
                                        "type": "string",
                                        "description": "Standardized food name",
                                    },
                                    "quantity": {
                                        "type": "number",
                                        "description": "Numeric quantity",
                                    },
                                    "unit": {
                                        "type": "string",
                                        "description": "Measurement unit",
                                    },
                                    "original_text": {
                                        "type": "string",
                                        "description": "Original text snippet",
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "description": "Confidence 0.0-1.0",
                                    },
                                    "search_terms": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Alternative search terms for database lookup (e.g., for 'overnight oats': ['overnight oats', 'oats', 'oatmeal', 'rolled oats'])",
                                    },
                                },
                                "required": [
                                    "food_name",
                                    "quantity",
                                    "unit",
                                    "confidence",
                                    "search_terms",
                                ],
                            },
                        },
                        "meal_detected": {
                            "type": "string",
                            "enum": [
                                "breakfast",
                                "lunch",
                                "dinner",
                                "snack",
                                "unknown",
                            ],
                            "description": "Detected meal context",
                        },
                    },
                    "required": ["items"],
                },
            }
        ]

        # Build user message with optional meal hint
        user_message = text
        if meal_hint:
            user_message = f"Meal: {meal_hint}\nInput: {text}"

        # Call Claude API with tool calling (wrapped to prevent blocking)
        # Model ID configurable via ANTHROPIC_MODEL env var
        response = await asyncio.to_thread(
            client.messages.create,
            model=settings.anthropic_model,
            max_tokens=AI_MAX_TOKENS,
            system=FoodResolverService.SYSTEM_PROMPT,
            tools=tools,
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract tool call result
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_food_items":
                tool_use_block = block
                break

        if not tool_use_block:
            raise ValueError("AI could not parse food items from input")

        result = tool_use_block.input
        items_data = result.get("items", [])

        if not items_data:
            raise ValueError("No food items could be extracted from input")

        # Convert to Pydantic models
        parsed_items = [ParsedFoodItem(**item) for item in items_data]

        # Extract meal context
        meal_detected = result.get("meal_detected", "unknown")
        meal_name = None if meal_detected == "unknown" else meal_detected

        logger.info(f"Parsed {len(parsed_items)} food items (meal: {meal_name})")

        return parsed_items, meal_name

    @staticmethod
    def _match_unit_to_portion(
        user_unit: str, portions: list[FoodPortion]
    ) -> FoodPortion | None:
        """
        Match a user's unit string to an available portion.

        Priority:
        1. Exact match on unit_name
        2. Exact match on modifier (first word)
        3. Partial match on modifier (e.g., "breast" in "breast, bone removed")

        Args:
            user_unit: User's unit (e.g., "breast", "cup", "piece", "large")
            portions: Available portions for the food

        Returns:
            Best matching portion, or None if no match
        """
        user_unit_lower = user_unit.lower().strip()

        # Common unit aliases
        aliases = {
            "cups": "cup",
            "tablespoons": "tablespoon",
            "tbsp": "tablespoon",
            "teaspoons": "teaspoon",
            "tsp": "teaspoon",
            "pieces": "piece",
            "slices": "slice",
            "breasts": "breast",
            "oz": "ounce",
            "ounces": "ounce",
            "lbs": "pound",
            "pounds": "pound",
            "serving": "serving",
            "servings": "serving",
            "eggs": "egg",
            "cookies": "piece",  # Treat cookies as pieces
            "cookie": "piece",
            "bananas": "banana",
            "banana": "piece",  # Fallback: bananas as pieces (1 banana ~ 1 piece)
            "pieces of": "piece",
            "item": "piece",
            "items": "piece",
        }
        normalized_unit = aliases.get(user_unit_lower, user_unit_lower)

        # Priority 1: Exact match on unit_name
        for portion in portions:
            unit_name_lower = (portion.unit_name or "").lower()
            if normalized_unit == unit_name_lower:
                logger.debug(f"Exact match on unit_name: {portion.unit_name}")
                return portion

        # Priority 2: Exact match on modifier (first word or whole)
        # This handles "large", "small", "medium" for eggs
        for portion in portions:
            modifier_lower = (portion.modifier or "").lower()
            # Check if modifier equals or starts with the unit
            modifier_first_word = modifier_lower.split()[0] if modifier_lower else ""
            if normalized_unit == modifier_lower or normalized_unit == modifier_first_word:
                logger.debug(f"Exact match on modifier: {portion.modifier}")
                return portion

        # Priority 3: Partial match on modifier (e.g., "breast" in "breast, bone removed")
        # But NOT in descriptions that are unrelated (e.g., "cup (4.86 large eggs)")
        for portion in portions:
            modifier_lower = (portion.modifier or "").lower()
            # Only match if it's a significant portion of the modifier
            if modifier_lower and normalized_unit in modifier_lower.split(",")[0]:
                logger.debug(f"Partial match on modifier: {portion.modifier}")
                return portion

        # Priority 4: Generic "piece" or "serving" as fallback
        if normalized_unit in ("piece", "serving"):
            for portion in portions:
                unit_name_lower = (portion.unit_name or "").lower()
                if "piece" in unit_name_lower or "serving" in unit_name_lower:
                    logger.debug(f"Fallback match on piece/serving: {portion.unit_name}")
                    return portion

        return None

    @staticmethod
    def _build_portion_options(portions: list[FoodPortion]) -> list[PortionOption]:
        """
        Convert FoodPortion models to PortionOption schemas.

        Args:
            portions: List of FoodPortion models

        Returns:
            List of PortionOption schemas
        """
        options = []
        for p in portions:
            # Build display name
            unit_part = p.modifier if p.modifier else p.unit_name
            display_name = f"{float(p.amount)} {unit_part} ({float(p.gram_weight)}g)"

            option = PortionOption(
                portion_id=p.id,
                amount=float(p.amount),
                unit_name=p.unit_name,
                modifier=p.modifier,
                gram_weight=float(p.gram_weight),
                display_name=display_name,
            )
            options.append(option)
        return options

    # ------------------------------------------------------------------
    # Token-level scoring helpers (keyword layer 2)
    # ------------------------------------------------------------------

    @staticmethod
    def _token_score(query: str, food_name: str) -> float:
        """
        Multi-signal token scoring for a query against a food name.

        Returns a bonus score in [0, ~0.5] that gets added to the trigram
        similarity to form the final keyword score.
        """
        name = food_name.lower()
        q = query.lower()
        score = 0.0

        # Exact match
        if name == q:
            return 1.0

        # Starts with query
        if name.startswith(q):
            score += TOKEN_STARTS_WITH_BONUS

        # Query appears as whole word/token
        tokens = _re.split(r"[\s,]+", name)
        if any(t.startswith(q) for t in tokens):
            score += TOKEN_WORD_BONUS

        # Length penalty — prefer shorter, simpler names
        score -= len(name) * LENGTH_PENALTY_FACTOR

        return max(score, 0.0)

    # ------------------------------------------------------------------
    # Hybrid search: keyword + semantic
    # ------------------------------------------------------------------

    @staticmethod
    async def match_food_in_database(
        db: AsyncSession,
        food_name: str,
        max_results: int = AI_MAX_MATCHES_PER_ITEM,
        user_unit: str | None = None,
        user_quantity: float = 1.0,
        search_terms: list[str] | None = None,
    ) -> list[FoodMatchOption]:
        """
        Find matching foods using hybrid search (keyword + semantic).

        Layer 1 — Keyword: pg_trgm similarity + token-level scoring
        Layer 2 — Semantic: pgvector cosine similarity (Cohere / Ollama)
        Final score = KEYWORD_WEIGHT * keyword + SEMANTIC_WEIGHT * semantic

        Falls back to keyword-only if embedding fails.
        """
        # Build list of all search terms
        all_terms = [food_name]
        if search_terms:
            for term in search_terms:
                if term and term.lower() != food_name.lower() and term not in all_terms:
                    all_terms.append(term)

        logger.info(f"Hybrid search with terms: {all_terms}")

        # ----------------------------------------------------------
        # Layer 1: Keyword search (trigram + token scoring)
        # ----------------------------------------------------------
        # Dict: food_id -> (Food, best_keyword_score, matched_term)
        food_results: dict[int, tuple[Food, float, str]] = {}

        for term in all_terms:
            portion_count = (
                select(func.count(FoodPortion.id))
                .where(FoodPortion.food_id == Food.id)
                .correlate(Food)
                .scalar_subquery()
            )

            similarity = func.similarity(Food.name, term)

            query = (
                select(Food, similarity.label("sim"))
                .options(
                    selectinload(Food.food_nutrients).selectinload(
                        FoodNutrient.nutrient
                    ),
                    selectinload(Food.portions),
                )
                .where(similarity > FOOD_MATCH_SIMILARITY_THRESHOLD)
                .order_by(
                    (func.lower(Food.name) == func.lower(term)).desc(),
                    Food.created_by_user_id.isnot(None).desc(),
                    similarity.desc(),
                    portion_count.desc(),
                )
                .limit(max_results * 2)  # Fetch extra for re-ranking
            )

            result = await db.execute(query)
            rows = result.all()

            for food, sim_score in rows:
                # Combine trigram similarity with token scoring
                token_bonus = FoodResolverService._token_score(term, food.name)
                keyword_score = min(float(sim_score) + token_bonus, 1.0)

                if (
                    food.id not in food_results
                    or keyword_score > food_results[food.id][1]
                ):
                    food_results[food.id] = (food, keyword_score, term)

        # ----------------------------------------------------------
        # Layer 2: Semantic search (embedding cosine similarity)
        # ----------------------------------------------------------
        semantic_scores: dict[int, float] = {}
        embedding_col = None

        try:
            query_vec, provider = await embed_query(food_name)
            embedding_col = (
                "embedding_cohere"
                if provider == EmbeddingProvider.COHERE
                else "embedding_ollama"
            )

            # Format vector for pgvector
            vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"

            # Use a savepoint so SQL errors (e.g., missing column) don't
            # poison the outer transaction in asyncpg.
            async with db.begin_nested():
                sem_query = text(
                    f"SELECT id, 1 - ({embedding_col} <=> CAST(:vec AS vector)) AS cosine_sim "
                    f"FROM foods "
                    f"WHERE {embedding_col} IS NOT NULL "
                    f"ORDER BY {embedding_col} <=> CAST(:vec AS vector) "
                    f"LIMIT :lim"
                )
                sem_result = await db.execute(
                    sem_query, {"vec": vec_str, "lim": max_results * 3}
                )

                for row in sem_result.fetchall():
                    food_id, cosine_sim = row
                    semantic_scores[food_id] = max(float(cosine_sim), 0.0)

            logger.info(
                f"Semantic search returned {len(semantic_scores)} results via {provider.value}"
            )

        except Exception as e:
            logger.warning(f"Semantic search failed, using keyword-only: {e}")

        # ----------------------------------------------------------
        # Score fusion
        # ----------------------------------------------------------
        # Collect all candidate food IDs from both layers
        all_food_ids = set(food_results.keys()) | set(semantic_scores.keys())

        # For foods found only by semantic search, we need to load them
        missing_ids = all_food_ids - set(food_results.keys())
        if missing_ids:
            load_query = (
                select(Food)
                .options(
                    selectinload(Food.food_nutrients).selectinload(
                        FoodNutrient.nutrient
                    ),
                    selectinload(Food.portions),
                )
                .where(Food.id.in_(list(missing_ids)))
            )
            load_result = await db.execute(load_query)
            for food in load_result.scalars().all():
                food_results[food.id] = (food, 0.0, food_name)

        # Compute final scores
        scored: list[tuple[Food, float, str]] = []
        has_semantic = bool(semantic_scores)

        for food_id, (food, kw_score, matched_term) in food_results.items():
            sem_score = semantic_scores.get(food_id, 0.0)

            if has_semantic:
                final = KEYWORD_WEIGHT * kw_score + SEMANTIC_WEIGHT * sem_score
            else:
                final = kw_score  # Keyword-only fallback

            # Boost custom foods slightly
            if food.created_by_user_id is not None:
                final += 0.05

            # Boost foods with portions
            if food.portions:
                final += 0.02

            scored.append((food, min(final, 1.0), matched_term))

        # Sort by final score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:max_results]

        logger.info(
            f"Hybrid search: {len(scored)} results "
            f"(keyword candidates: {len(food_results)}, "
            f"semantic candidates: {len(semantic_scores)})"
        )

        # ----------------------------------------------------------
        # Build match options
        # ----------------------------------------------------------
        matches = []
        for food, final_score, matched_term in scored:
            nutrients_map = {}
            for fn in food.food_nutrients:
                if fn.nutrient:
                    nutrient_name = fn.nutrient.name.lower()
                    if "energy" in nutrient_name or "calorie" in nutrient_name:
                        nutrients_map["calories"] = fn.amount_per_serving
                    elif "protein" in nutrient_name:
                        nutrients_map["protein"] = fn.amount_per_serving
                    elif (
                        "carbohydrate" in nutrient_name
                        and "by difference" in nutrient_name
                    ):
                        nutrients_map["carbs"] = fn.amount_per_serving
                    elif (
                        "total lipid" in nutrient_name
                        or "fat, total" in nutrient_name
                    ):
                        nutrients_map["fat"] = fn.amount_per_serving

            portion_options = FoodResolverService._build_portion_options(food.portions)

            match = FoodMatchOption(
                food_id=food.id,
                name=food.name,
                serving_size=food.serving_size or 100.0,
                unit=food.unit or "g",
                similarity_score=round(final_score, 3),
                calories=nutrients_map.get("calories"),
                protein=nutrients_map.get("protein"),
                carbs=nutrients_map.get("carbs"),
                fat=nutrients_map.get("fat"),
                quantity_multiplier=1.0,
                portions=portion_options,
                matched_portion=None,
                calculated_grams=None,
            )
            matches.append(match)

        return matches

    @staticmethod
    async def get_meal_by_name(db: AsyncSession, meal_name: str) -> Meal | None:
        """
        Look up standard meal by name.

        Args:
            db: Database session
            meal_name: Meal name (e.g., "breakfast", "lunch")

        Returns:
            Meal object if found, None otherwise
        """
        result = await db.execute(
            select(Meal).where(func.lower(Meal.name) == func.lower(meal_name.strip()))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def resolve_foods(
        db: AsyncSession,
        text: str,
        meal_hint: str | None = None,
        max_matches_per_item: int = 3,
    ) -> FoodResolveResponse:
        """
        Main orchestrator: parse text with AI, match foods in database.

        Args:
            db: Database session
            text: Natural language food description
            meal_hint: Optional meal context hint
            max_matches_per_item: Max database matches per item

        Returns:
            Complete resolution response with matches

        Raises:
            ValueError: If parsing fails or input invalid
            anthropic.APIError: If AI service fails
        """
        # Step 1: Parse with AI
        parsed_items, detected_meal_name = await FoodResolverService.parse_food_text(
            text, meal_hint
        )

        # Step 2: Match each item in database
        resolved_items = []
        confidence_scores = []

        for parsed_item in parsed_items:
            matches = await FoodResolverService.match_food_in_database(
                db,
                parsed_item.food_name,
                max_matches_per_item,
                user_unit=parsed_item.unit,
                user_quantity=parsed_item.quantity,
                search_terms=parsed_item.search_terms,
            )

            # Determine status
            if not matches:
                status = "not_found"
            elif (
                len(matches) == 1
                and matches[0].similarity_score > AI_HIGH_SIMILARITY_THRESHOLD
            ):
                status = "matched"
            else:
                status = (
                    "ambiguous"
                    if parsed_item.confidence < AI_LOW_CONFIDENCE_THRESHOLD
                    else "matched"
                )

            resolved_item = ResolvedFoodItem(
                parsed_item=parsed_item, matches=matches, status=status
            )
            resolved_items.append(resolved_item)
            confidence_scores.append(parsed_item.confidence)

        # Step 3: Look up meal context
        meal_context = None
        meal_name_to_lookup = meal_hint or detected_meal_name
        if meal_name_to_lookup:
            meal = await FoodResolverService.get_meal_by_name(db, meal_name_to_lookup)
            if meal:
                meal_context = MealContext(meal_id=meal.id, meal_name=meal.name)

        # Step 4: Calculate overall confidence
        overall_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0.0
        )

        return FoodResolveResponse(
            original_text=text,
            resolved_items=resolved_items,
            meal_context=meal_context,
            overall_confidence=round(overall_confidence, 2),
            ai_provider="anthropic",
        )

    @staticmethod
    def convert_to_multi_food_confirmation(
        response: FoodResolveResponse,
    ) -> MultiFoodConfirmationResponse:
        """
        Convert FoodResolveResponse to MultiFoodConfirmationResponse.

        Flattens the nested structure, generates UUIDs, guesses meal, and deduplicates.

        Args:
            response: Original resolve response

        Returns:
            Flattened multi-food confirmation response
        """
        import uuid
        from datetime import datetime

        # Guess meal based on current time
        now = datetime.now()
        hour = now.hour

        if hour < 11:
            guessed_meal = "Breakfast"
        elif 11 <= hour < 15:
            guessed_meal = "Lunch"
        elif 15 <= hour < 20:
            guessed_meal = "Dinner"
        else:
            guessed_meal = "Snack"

        # Override with meal context if available
        if response.meal_context and response.meal_context.meal_name:
            guessed_meal = response.meal_context.meal_name.title()

        food_items = []

        for resolved_item in response.resolved_items:
            parsed = resolved_item.parsed_item
            matches = resolved_item.matches

            # Apply deduplication: prefer non-100g servings
            deduplicated_matches = FoodResolverService._deduplicate_matches(matches)

            # Select the top match as default (if any)
            selected_match = deduplicated_matches[0] if deduplicated_matches else None

            # Build alternatives list (exclude the selected one)
            alternatives = []
            for idx, match in enumerate(deduplicated_matches):
                if idx == 0:
                    continue  # Skip the selected match
                alt_entry = {
                    "food_id": match.food_id,
                    "name": match.name,
                    "serving_size": match.serving_size,
                    "unit": match.unit,
                    "calories": match.calories,
                    "protein": match.protein,
                    "fat": match.fat,
                    "similarity_score": match.similarity_score,
                }
                # Include full portions for alternatives (needed for unit detection)
                if match.portions:
                    alt_entry["portions"] = [
                        {
                            "portion_id": p.portion_id,
                            "amount": p.amount,
                            "unit_name": p.unit_name,
                            "modifier": p.modifier,
                            "gram_weight": p.gram_weight,
                            "display_name": p.display_name,
                        }
                        for p in match.portions[:10]  # Limit to top 10 portions
                    ]
                alternatives.append(alt_entry)

            # Use the food's default portion, not the parsed quantity/unit
            # This ensures "100 cookies" becomes "1 cookie" with weight from DB
            display_quantity = 1.0  # Always 1 unit of the food's portion
            display_unit = parsed.unit  # Keep parsed unit for display, but will be overridden below
            weight_grams = None
            
            serving_size = selected_match.serving_size if selected_match else None
            serving_unit = selected_match.unit if selected_match else None

            # Build portions list for this item
            item_portions = []
            if selected_match and selected_match.portions:
                item_portions = [
                    {
                        "portion_id": p.portion_id,
                        "amount": p.amount,
                        "unit_name": p.unit_name,
                        "modifier": p.modifier,
                        "gram_weight": p.gram_weight,
                        "display_name": p.display_name,
                    }
                    for p in selected_match.portions
                ]
                
                # Use the FIRST portion as the default display
                # This gives us the proper unit_name and gram_weight
                first_portion = item_portions[0]
                display_unit = first_portion["unit_name"]  # Override with food's actual unit
                display_quantity = first_portion["amount"]  # Use portion amount
                weight_grams = first_portion["gram_weight"]  # Pre-populate weight from portion

            # Create flattened item
            item = MultiFoodConfirmationItem(
                item_id=str(uuid.uuid4()),
                raw_text=parsed.original_text or parsed.food_name,
                parsed_quantity=display_quantity,  # Use 1 unit, not parsed quantity
                parsed_unit=display_unit,  # Use food's actual unit
                confidence=parsed.confidence,
                selected_food_id=selected_match.food_id if selected_match else None,
                selected_name=selected_match.name if selected_match else None,
                serving_size=serving_size,
                serving_unit=serving_unit,
                calories=selected_match.calories if selected_match else None,
                protein=selected_match.protein if selected_match else None,
                fat=selected_match.fat if selected_match else None,
                fiber=None,  # Not currently tracked in FoodMatchOption
                weight_grams=weight_grams,  # Pre-populate from food's portion
                portions=item_portions,
                alternatives=alternatives,
                status=resolved_item.status,
            )
            food_items.append(item)

        return MultiFoodConfirmationResponse(
            original_text=response.original_text,
            food_items=food_items,
            guessed_meal=guessed_meal,
            overall_confidence=response.overall_confidence,
        )

    @staticmethod
    def _deduplicate_matches(matches: list[FoodMatchOption]) -> list[FoodMatchOption]:
        """
        Deduplicate food matches, preferring human-readable portions over 100g.

        Args:
            matches: List of food match options

        Returns:
            Deduplicated list
        """
        seen_names = {}
        for match in matches:
            name = match.name
            serving_size = match.serving_size

            if name not in seen_names:
                # First time seeing this name - add it
                seen_names[name] = match
            else:
                # Duplicate found - prefer non-100g portion
                existing_serving = seen_names[name].serving_size
                if existing_serving == 100.0 and serving_size != 100.0:
                    # Replace 100g with human-readable portion
                    seen_names[name] = match
                    logger.info(
                        f"Replaced 100g serving with {serving_size}g for '{name}'"
                    )

        return list(seen_names.values())
