"""Photo food recognition via Claude Vision API."""

import base64
import json
import os
import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)



RECOGNITION_PROMPT = """Analyze this food photo. It may be a photo of food OR a nutrition label.

For NUTRITION LABELS: extract ALL visible data exactly as printed.
For FOOD PHOTOS: identify each food item and estimate nutrition.

Rules for serving size:
- Include quantity + unit (e.g. "1 bottle", "2 slices")
- Include volume if printed/obvious (e.g. "11 fl oz")
- Include weight if printed; if not printed, estimate weight in grams
- Format: "1 bottle (11 fl oz, 335g)" or "1 cup (240g)"

Return ALL nutrients you can find or estimate. Required: calories, protein, fat, carbs, fiber.
Optional (include if on label or estimable): saturated_fat, trans_fat, cholesterol_mg, sodium_mg, sugars, added_sugars, vitamin_d_mcg, calcium_mg, iron_mg, potassium_mg.

Respond ONLY with valid JSON:
{
  "is_nutrition_label": true/false,
  "items": [
    {
      "name": "Chocolate Protein Shake",
      "serving_description": "1 bottle (11 fl oz, 335g)",
      "serving_size_g": 335,
      "confidence": "high",
      "nutrients": {
        "calories": 140,
        "protein_g": 30,
        "fat_g": 1.5,
        "saturated_fat_g": 0.5,
        "carbs_g": 7,
        "fiber_g": 4,
        "sugars_g": 1,
        "sodium_mg": 320,
        "cholesterol_mg": 10
      }
    }
  ]
}

For food photos with multiple items, return one entry per distinct food.
Only include nutrient fields you can confidently extract or estimate."""


@dataclass
class RecognizedItem:
    name: str
    serving_description: str
    serving_size_g: float
    confidence: str
    nutrients: dict[str, float]  # e.g. {"calories": 140, "protein_g": 30, ...}


@dataclass
class RecognitionResult:
    is_nutrition_label: bool
    items: list[RecognizedItem]


async def recognize_food_photo(image_data: bytes, media_type: str = "image/jpeg") -> RecognitionResult:
    """Send a food photo to Claude Vision for recognition.
    
    Args:
        image_data: Raw image bytes
        media_type: MIME type (image/jpeg, image/png, image/webp)
    
    Returns:
        RecognitionResult with identified foods or nutrition label data
    """
    from whati8.config import settings
    
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    ANTHROPIC_API_KEY = settings.anthropic_api_key
    ANTHROPIC_MODEL = settings.anthropic_model

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    
    b64_image = base64.standard_b64encode(image_data).decode("utf-8")

    message = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": RECOGNITION_PROMPT,
                    },
                ],
            }
        ],
    )

    # Parse response
    response_text = message.content[0].text.strip()
    
    # Extract JSON from potential markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        response_text = "\n".join(json_lines)

    data = json.loads(response_text)

    items = [
        RecognizedItem(
            name=item["name"],
            serving_description=item.get("serving_description", "1 serving"),
            serving_size_g=item.get("serving_size_g", 100),
            confidence=item.get("confidence", "medium"),
            nutrients=item.get("nutrients", {}),
        )
        for item in data.get("items", [])
    ]

    return RecognitionResult(
        is_nutrition_label=data.get("is_nutrition_label", False),
        items=items,
    )
