"""Service for AI-powered natural language food resolution."""

import json
from typing import Any

from anthropic import Anthropic
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.config import settings
from whati8.models.food import Food
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.meal import Meal
from whati8.schemas.food_resolver import (
    ParsedFoodItem,
    FoodMatchOption,
    ResolvedFoodItem,
    MealContext,
    FoodResolveResponse,
)


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

Extract all food items from the input text."""

    @staticmethod
    def parse_food_text(
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
                                },
                                "required": [
                                    "food_name",
                                    "quantity",
                                    "unit",
                                    "confidence",
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

        # Call Claude API with tool calling
        # Model ID configurable via ANTHROPIC_MODEL env var
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
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

        return parsed_items, meal_name

    @staticmethod
    async def match_food_in_database(
        db: AsyncSession, food_name: str, max_results: int = 3
    ) -> list[FoodMatchOption]:
        """
        Find matching foods in database using fuzzy search.

        Args:
            db: Database session
            food_name: Food name to search for
            max_results: Maximum number of matches to return

        Returns:
            List of matching foods with similarity scores
        """
        # Fuzzy search using pg_trgm (reuse pattern from food router)
        query = (
            select(Food)
            .options(
                selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient)
            )
            .where(func.similarity(Food.name, food_name) > 0.3)
            .order_by(func.similarity(Food.name, food_name).desc())
            .limit(max_results)
        )

        result = await db.execute(query)
        foods = result.scalars().all()

        # Convert to match options with nutrient preview
        matches = []
        for food in foods:
            # Calculate similarity score
            similarity_result = await db.execute(
                select(func.similarity(Food.name, food_name)).where(Food.id == food.id)
            )
            similarity_score = similarity_result.scalar() or 0.0

            # Extract key nutrients
            nutrients_map = {}
            for fn in food.food_nutrients:
                if fn.nutrient:
                    nutrient_name = fn.nutrient.name.lower()
                    # Map common nutrient names
                    if "energy" in nutrient_name or "calorie" in nutrient_name:
                        nutrients_map["calories"] = fn.amount
                    elif "protein" in nutrient_name:
                        nutrients_map["protein"] = fn.amount
                    elif (
                        "carbohydrate" in nutrient_name
                        and "by difference" in nutrient_name
                    ):
                        nutrients_map["carbs"] = fn.amount
                    elif "total lipid" in nutrient_name or "fat, total" in nutrient_name:
                        nutrients_map["fat"] = fn.amount

            match = FoodMatchOption(
                food_id=food.id,
                name=food.name,
                serving_size=food.serving_size or 100.0,
                unit=food.serving_unit or "g",
                similarity_score=round(similarity_score, 2),
                calories=nutrients_map.get("calories"),
                protein=nutrients_map.get("protein"),
                carbs=nutrients_map.get("carbs"),
                fat=nutrients_map.get("fat"),
                quantity_multiplier=1.0,  # User can adjust based on their quantity
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
            select(Meal).where(
                func.lower(Meal.name) == func.lower(meal_name.strip())
            )
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
        parsed_items, detected_meal_name = FoodResolverService.parse_food_text(
            text, meal_hint
        )

        # Step 2: Match each item in database
        resolved_items = []
        confidence_scores = []

        for parsed_item in parsed_items:
            matches = await FoodResolverService.match_food_in_database(
                db, parsed_item.food_name, max_matches_per_item
            )

            # Determine status
            if not matches:
                status = "not_found"
            elif len(matches) == 1 and matches[0].similarity_score > 0.8:
                status = "matched"
            else:
                status = "ambiguous" if parsed_item.confidence < 0.7 else "matched"

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
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        )

        return FoodResolveResponse(
            original_text=text,
            resolved_items=resolved_items,
            meal_context=meal_context,
            overall_confidence=round(overall_confidence, 2),
            ai_provider="anthropic",
        )
