"""NutrientCalculator — single source of truth for nutrient computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class NutrientInput:
    """Input for nutrient computation. food can be a Food model or any object with
    food_nutrients, serving_size, created_by_user_id, and portions attributes."""
    food: Any  # Food model or duck-typed equivalent
    quantity: float
    unit: str


# ── Name-based classifiers ─────────────────────────────────────────────────────


def _is_energy(name: str) -> bool:
    n = name.lower()
    return n.startswith("energy") or "atwater" in n


def _is_carb(name: str) -> bool:
    return "carbohydrate" in name.lower()


# Maps friendly keys to name-matching functions.
# "calories" and "carbs" are listed here for completeness but are handled
# separately via coalescing logic in compute_item_nutrients (they need
# priority-based selection, not simple summing). Other keys use the matcher
# directly to sum matching nutrients.
FRIENDLY_MAP: dict[str, Callable[[str], bool]] = {
    "calories": _is_energy,  # coalesced: Atwater General > Specific > Plain
    "protein": lambda n: n.lower() == "protein",
    "fat": lambda n: "lipid" in n.lower() or n.lower() == "fat",
    "fiber": lambda n: "fiber" in n.lower(),
    "carbs": _is_carb,  # coalesced: by summation > by difference
}


# ── Formula evaluation ─────────────────────────────────────────────────────────


def _eval_formula(formula: str, values: dict[str, float]) -> float:
    """Evaluate a formula with friendly values as namespace.

    Uses Python's built-in eval with a restricted namespace so that
    single-arg round() works naturally: round(1.65) == 2.

    Security: Formulas are user-authored via UserSummaryNutrient config, writable
    only by the authenticated user for their own account. The restricted __builtins__
    mitigates casual injection but is NOT a full sandbox. If formulas ever become
    shareable or publicly editable, replace eval with a proper expression parser
    (e.g., simpleeval or ast-based).
    """
    namespace = {
        **values,
        "round": round,
        "min": min,
        "max": max,
        "abs": abs,
    }
    try:
        result = eval(formula, {"__builtins__": {}}, namespace)  # noqa: S307
        return float(result)
    except Exception:
        return 0.0


# ── Scaling helpers ────────────────────────────────────────────────────────────


def _get_gram_weight(food: Any, quantity: float, unit: str) -> float:
    """Resolve quantity + unit to grams."""
    import re

    unit_lower = unit.lower().strip()

    if unit_lower in ("grams", "g"):
        return float(quantity)

    # Strip leading quantity prefix from unit for matching
    # e.g., "1 bottle (325g)" → "bottle (325g)"
    unit_stripped = re.sub(r'^[\d.]+\s+', '', unit_lower)

    # Named portion lookup
    for portion in food.portions or []:
        portion_unit = (portion.unit_name or "").lower().strip()
        portion_desc = (portion.portion_description or "").lower().strip()
        modifier = (portion.modifier or "").lower().strip()
        # Also strip leading quantity prefix from portion descriptions
        desc_stripped = re.sub(r'^[\d.]+\s+', '', portion_desc)

        candidates = {portion_unit, portion_desc, modifier, desc_stripped}
        if unit_lower in candidates or unit_stripped in candidates:
            # gram_weight may cover `amount` units (e.g., "2 cookies = 30g").
            # Per-unit weight = gram_weight / amount.
            per_unit = float(portion.gram_weight) / float(portion.amount or 1)
            return per_unit * float(quantity)

    # Fallback: treat quantity as grams
    return float(quantity)


def _scale_factor(food: Any, gram_weight: float) -> float:
    """Scale factor relative to the food's base amount."""
    if food.created_by_user_id is None:
        # USDA food: nutrients per 100 g
        base = 100.0
    else:
        # Custom food: nutrients per serving_size
        base = float(food.serving_size) if food.serving_size else 100.0

    return gram_weight / base if base else 0.0


# ── Per-item computation ───────────────────────────────────────────────────────


def compute_item_nutrients(
    item: NutrientInput,
) -> tuple[dict[str, float], dict[int, float]]:
    """Return (friendly_values, {nutrient_id: scaled_amount}) for one item."""
    food = item.food
    gram_weight = _get_gram_weight(food, item.quantity, item.unit)
    scale = _scale_factor(food, gram_weight)

    named: dict[str, float] = {}  # nutrient name → scaled amount
    by_id: dict[int, float] = {}  # nutrient_id → scaled amount

    for fn in food.food_nutrients or []:
        name = fn.nutrient.name
        amount = float(fn.amount_per_serving) * scale
        named[name] = amount
        by_id[fn.nutrient_id] = amount

    # ── Energy coalescing ──────────────────────────────────────────────────
    energy_general: float | None = None
    energy_specific: float | None = None
    energy_plain: float | None = None

    for name, amount in named.items():
        n = name.lower()
        if "atwater general" in n:
            energy_general = amount
        elif "atwater specific" in n:
            energy_specific = amount
        elif n.startswith("energy"):
            energy_plain = amount

    if energy_general is not None:
        calories = energy_general
    elif energy_specific is not None:
        calories = energy_specific
    else:
        calories = energy_plain if energy_plain is not None else 0.0

    # ── Carb coalescing ────────────────────────────────────────────────────
    carb_summation: float | None = None
    carb_difference: float | None = None

    for name, amount in named.items():
        n = name.lower()
        if "carbohydrate" in n:
            if "summation" in n:
                carb_summation = amount
            elif "difference" in n:
                carb_difference = amount

    carbs = carb_summation if carb_summation is not None else max(carb_difference or 0.0, 0.0)

    # ── Friendly values ────────────────────────────────────────────────────
    friendly: dict[str, float] = {"calories": calories, "carbs": carbs}

    for key, matcher in FRIENDLY_MAP.items():
        if key in ("calories", "carbs"):
            continue
        val = sum(amount for name, amount in named.items() if matcher(name))
        friendly[key] = val

    return friendly, by_id


# ── NutrientCalculator ─────────────────────────────────────────────────────────


class NutrientCalculator:
    @staticmethod
    def compute_summary(
        items: list[NutrientInput],
        config: list,
        formula_mode: str = "per_item",
    ) -> list[dict]:
        """Compute nutrient summary for any collection of foods.

        Pipeline:
        1. Scale nutrients for each item
        2. Coalesce energy (Atwater General > Specific > Plain) per item
        3. Coalesce carbs (by summation > by difference) per item
        4. Build friendly values dict per item
        5. Apply config:
           - formula, per_item: sum(formula(item) for item in items)
           - formula, total:    formula(sum of all items)
           - nutrient_id:       sum scaled values matching id across items
        6. Return list of {"name": ..., "value": ..., "unit": ...}
        """
        if not config:
            return []

        item_friendlies: list[dict[str, float]] = []
        item_by_ids: list[dict[int, float]] = []

        for item in items:
            friendly, by_id = compute_item_nutrients(item)
            item_friendlies.append(friendly)
            item_by_ids.append(by_id)

        return NutrientCalculator.compute_summary_from_precomputed(
            item_friendlies, item_by_ids, config, formula_mode
        )

    @staticmethod
    def compute_summary_from_precomputed(
        item_friendlies: list[dict[str, float]],
        item_by_ids: list[dict[int, float]],
        config: list,
        formula_mode: str = "per_item",
    ) -> list[dict]:
        """Apply config to pre-computed nutrient data.

        Use when you've already called compute_item_nutrients() and want to
        avoid recomputing. Same config application as compute_summary().
        """
        if not config:
            return []

        # Pre-compute summed friendly values for total mode
        total_friendly: dict[str, float] = {k: 0.0 for k in FRIENDLY_MAP}
        for f in item_friendlies:
            for k in FRIENDLY_MAP:
                total_friendly[k] += f.get(k, 0.0)

        results = []
        for cfg in config:
            name = cfg.display_name
            unit = cfg.display_unit

            if cfg.formula:
                if formula_mode == "total":
                    value = _eval_formula(cfg.formula, total_friendly)
                else:  # per_item (default)
                    value = sum(_eval_formula(cfg.formula, f) for f in item_friendlies)
            elif cfg.nutrient_id is not None:
                value = sum(by_id.get(cfg.nutrient_id, 0.0) for by_id in item_by_ids)
            else:
                value = 0.0

            results.append({"name": name, "value": value, "unit": unit})

        return results
