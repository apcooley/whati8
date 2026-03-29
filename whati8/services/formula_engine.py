"""
Formula DSL engine for custom summary metrics.

Supports:
- Nutrient references by friendly name: Calories, Protein, Carbs, Fat, Fiber
- Operators: + - * /
- Parentheses
- Functions: round(expr, unit), roundup(expr, unit), rounddown(expr, unit)
  where unit is the rounding increment (0.1, 0.5, 1, 5, etc.)

Example formulas:
  "Calories / 50"
  "round(Protein * 4 / Calories * 100, 1)"
  "roundup((Calories - Protein * 4 - Fat * 9) / 4, 0.5)"
"""

import ast
import math
import operator

# Map friendly names to USDA nutrient names (lowercase)
FRIENDLY_TO_USDA = {
    "calories": "energy",
    "protein": "protein",
    "carbs": "carbohydrate, by difference",
    "fat": "total lipid (fat)",
    "fiber": "fiber, total dietary",
    "sugar": "sugars, total including nlea",
    "sodium": "sodium, na",
    "cholesterol": "cholesterol",
    "saturated_fat": "fatty acids, total saturated",
    "potassium": "potassium, k",
    "calcium": "calcium, ca",
    "iron": "iron, fe",
    "vitamin_c": "vitamin c, total ascorbic acid",
    "vitamin_a": "vitamin a, rae",
}

# Reverse: USDA name -> friendly display name + unit
USDA_TO_FRIENDLY = {
    "energy": ("Calories", "kcal"),
    "protein": ("Protein", "g"),
    "carbohydrate, by difference": ("Carbs", "g"),
    "total lipid (fat)": ("Fat", "g"),
    "fiber, total dietary": ("Fiber", "g"),
    "sugars, total including nlea": ("Sugar", "g"),
    "sodium, na": ("Sodium", "mg"),
    "cholesterol": ("Cholesterol", "mg"),
    "fatty acids, total saturated": ("Sat Fat", "g"),
    "potassium, k": ("Potassium", "mg"),
    "calcium, ca": ("Calcium", "mg"),
    "iron, fe": ("Iron", "mg"),
    "vitamin c, total ascorbic acid": ("Vitamin C", "mg"),
    "vitamin a, rae": ("Vitamin A", "µg"),
}

# Special case: "energy" in kcal vs kJ
# USDA has two energy entries. We want kcal. The kcal one has unit="kcal".


def get_friendly_name(usda_name: str) -> tuple[str, str]:
    """Get (friendly_name, unit) for a USDA nutrient name."""
    key = usda_name.lower()
    if key in USDA_TO_FRIENDLY:
        return USDA_TO_FRIENDLY[key]
    return (usda_name, "")


def _round_to_unit(value: float, unit: float) -> float:
    """Round to nearest multiple of unit."""
    if unit <= 0:
        return value
    return round(value / unit) * unit


def _roundup_to_unit(value: float, unit: float) -> float:
    if unit <= 0:
        return value
    return math.ceil(value / unit) * unit


def _rounddown_to_unit(value: float, unit: float) -> float:
    if unit <= 0:
        return value
    return math.floor(value / unit) * unit


SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}

SAFE_FUNCS = {
    "round": _round_to_unit,
    "roundup": _roundup_to_unit,
    "rounddown": _rounddown_to_unit,
    "min": min,
    "max": max,
}


def evaluate_formula(formula: str, nutrient_values: dict[str, float]) -> float | None:
    """
    Evaluate a formula string against nutrient values.

    nutrient_values: {friendly_name_lower: value} e.g. {"calories": 1850, "protein": 120}

    Returns computed value or None if evaluation fails.
    """
    try:
        tree = ast.parse(formula, mode="eval")
        return _eval_node(tree.body, nutrient_values)
    except Exception:
        return None


def _eval_node(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.Name):
        key = node.id.lower()
        if key in values:
            return values[key]
        raise ValueError(f"Unknown nutrient: {node.id}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, values)
        right = _eval_node(node.right, values)
        op = SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        if isinstance(node.op, ast.Div) and right == 0:
            return 0.0
        return op(left, right)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, values)

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCS:
            args = [_eval_node(a, values) for a in node.args]
            return SAFE_FUNCS[node.func.id](*args)
        raise ValueError(f"Unknown function: {getattr(node.func, 'id', '?')}")

    raise ValueError(f"Unsupported expression: {type(node).__name__}")
