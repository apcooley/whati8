"""Tests for NutrientCalculator — single source of truth for nutrient computation.

Tests the core compute_summary() function across all use cases:
coalescing, scaling, portion matching, formula modes.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from whati8.services.nutrient_calculator import NutrientCalculator, NutrientInput


def _mock_nutrient(name, nutrient_id=None):
    """Create a mock Nutrient with a name."""
    n = MagicMock()
    n.name = name
    n.id = nutrient_id or id(n)  # unique default
    n.unit = "kcal" if "energy" in name.lower() else "g"
    return n


def _mock_food_nutrient(nutrient_name, amount, nutrient_id=None):
    """Create a mock FoodNutrient."""
    fn = MagicMock()
    fn.nutrient = _mock_nutrient(nutrient_name, nutrient_id)
    fn.nutrient_id = fn.nutrient.id
    fn.amount_per_serving = Decimal(str(amount))
    return fn


def _mock_food(name, serving_size=100, created_by_user_id=None, food_nutrients=None, portions=None):
    """Create a mock Food."""
    f = MagicMock()
    f.name = name
    f.serving_size = Decimal(str(serving_size))
    f.created_by_user_id = created_by_user_id
    f.unit = "g"
    f.food_nutrients = food_nutrients or []
    f.portions = portions or []
    return f


def _mock_portion(unit_name, gram_weight, amount=1, description=None):
    """Create a mock FoodPortion."""
    p = MagicMock()
    p.unit_name = unit_name
    p.gram_weight = Decimal(str(gram_weight))
    p.amount = Decimal(str(amount))
    p.portion_description = description or unit_name
    p.modifier = None
    return p


def _make_input(food, quantity=100, unit="grams"):
    """Create NutrientInput from a mock food."""
    return NutrientInput(
        food=food,
        quantity=quantity,
        unit=unit,
    )


def _mock_config_item(name, unit, nutrient_id=None, formula=None):
    """Create a mock UserSummaryNutrient config item."""
    c = MagicMock()
    c.display_name = name
    c.display_unit = unit
    c.nutrient_id = nutrient_id
    c.formula = formula
    c.display_order = 0
    return c


# ── Energy Coalescing ─────────────────────────────────────


class TestEnergyCoalescing:
    """Energy should coalesce: Atwater General > Atwater Specific > Plain Energy."""

    def test_plain_energy_only(self):
        """Food with only plain Energy returns that value."""
        food = _mock_food("Bread", food_nutrients=[
            _mock_food_nutrient("Energy", 265, nutrient_id=39),
            _mock_food_nutrient("Protein", 9),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 265) < 1

    def test_atwater_general_preferred_over_plain(self):
        """When both Atwater General and plain Energy exist, prefer Atwater General."""
        food = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy", 52, nutrient_id=39),
            _mock_food_nutrient("Energy (Atwater General Factors)", 60, nutrient_id=199),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 60) < 1

    def test_atwater_general_preferred_over_specific(self):
        """When all three exist, prefer Atwater General."""
        food = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy", 52, nutrient_id=39),
            _mock_food_nutrient("Energy (Atwater General Factors)", 60, nutrient_id=199),
            _mock_food_nutrient("Energy (Atwater Specific Factors)", 54, nutrient_id=200),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 60) < 1

    def test_atwater_specific_fallback(self):
        """When only Atwater Specific exists (no General, no plain), use it."""
        food = _mock_food("Exotic", food_nutrients=[
            _mock_food_nutrient("Energy (Atwater Specific Factors)", 54, nutrient_id=200),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 54) < 1

    def test_no_energy_returns_zero(self):
        """Food with no energy nutrients returns 0 for calories formula."""
        food = _mock_food("Salt", food_nutrients=[
            _mock_food_nutrient("Sodium, Na", 38758),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert cal["value"] == 0


# ── Scaling ───────────────────────────────────────────────


class TestScaling:
    """Nutrient scaling for USDA (per 100g) vs custom (per serving_size) foods."""

    def test_usda_food_100g_no_scaling(self):
        """100g of a USDA food should return raw amounts."""
        food = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy", 52),
            _mock_food_nutrient("Protein", 0.3),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food, quantity=100, unit="grams")], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 52) < 1

    def test_usda_food_200g_doubles(self):
        """200g of a USDA food should double the values."""
        food = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy", 52),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food, quantity=200, unit="grams")], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 104) < 1

    def test_custom_food_one_serving(self):
        """1 serving of a custom food (quantity=serving_size) returns raw amounts."""
        food = _mock_food("Protein Bar", serving_size=60, created_by_user_id=1, food_nutrients=[
            _mock_food_nutrient("Energy", 200),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food, quantity=60, unit="grams")], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 200) < 1

    def test_custom_food_half_serving(self):
        """Half a custom food serving should halve the values."""
        food = _mock_food("Protein Bar", serving_size=60, created_by_user_id=1, food_nutrients=[
            _mock_food_nutrient("Energy", 200),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food, quantity=30, unit="grams")], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 100) < 1


# ── Portion Matching ──────────────────────────────────────


class TestPortionMatching:
    """Portion-based quantity conversion."""

    def test_grams_unit(self):
        """Unit 'grams' uses quantity as gram weight directly."""
        food = _mock_food("Flour", food_nutrients=[
            _mock_food_nutrient("Energy", 364),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food, quantity=50, unit="grams")], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 182) < 1  # 364 * 50/100

    def test_portion_unit_lookup(self):
        """Named portion (e.g., 'slice') converts via portion gram_weight."""
        portions = [_mock_portion("slice", 30)]
        food = _mock_food("Bread", food_nutrients=[
            _mock_food_nutrient("Energy", 265),
        ], portions=portions)
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary(
            [_make_input(food, quantity=2, unit="slice")], config
        )
        cal = next(r for r in result if r["name"] == "Calories")
        assert abs(cal["value"] - 159) < 1  # 265 * (2*30)/100


# ── Formula Modes ─────────────────────────────────────────


class TestFormulaModes:
    """Formula application: per_item vs total."""

    def test_per_item_sums_individual_formulas(self):
        """per_item: sum(formula(item) for item in items)."""
        food1 = _mock_food("Food1", food_nutrients=[
            _mock_food_nutrient("Energy", 90),
            _mock_food_nutrient("Total lipid (fat)", 3),
            _mock_food_nutrient("Fiber, total dietary", 2),
        ])
        food2 = _mock_food("Food2", food_nutrients=[
            _mock_food_nutrient("Energy", 110),
            _mock_food_nutrient("Total lipid (fat)", 4),
            _mock_food_nutrient("Fiber, total dietary", 1),
        ])
        # WW formula: round(cal/50 + fat/12 - fiber/5)
        config = [_mock_config_item("WW", "points", formula="round(calories/50 + fat/12 - fiber/5)")]
        result = NutrientCalculator.compute_summary(
            [_make_input(food1), _make_input(food2)],
            config,
            formula_mode="per_item",
        )
        ww = next(r for r in result if r["name"] == "WW")
        # Food1: round(90/50 + 3/12 - 2/5) = round(1.8 + 0.25 - 0.4) = round(1.65) = 2
        # Food2: round(110/50 + 4/12 - 1/5) = round(2.2 + 0.33 - 0.2) = round(2.33) = 2
        # Total: 2 + 2 = 4
        assert ww["value"] == 4

    def test_total_applies_formula_to_sum(self):
        """total: formula(sum(items))."""
        food1 = _mock_food("Food1", food_nutrients=[
            _mock_food_nutrient("Energy", 90),
            _mock_food_nutrient("Total lipid (fat)", 3),
            _mock_food_nutrient("Fiber, total dietary", 2),
        ])
        food2 = _mock_food("Food2", food_nutrients=[
            _mock_food_nutrient("Energy", 110),
            _mock_food_nutrient("Total lipid (fat)", 4),
            _mock_food_nutrient("Fiber, total dietary", 1),
        ])
        config = [_mock_config_item("WW", "points", formula="round(calories/50 + fat/12 - fiber/5)")]
        result = NutrientCalculator.compute_summary(
            [_make_input(food1), _make_input(food2)],
            config,
            formula_mode="total",
        )
        ww = next(r for r in result if r["name"] == "WW")
        # Sum: cal=200, fat=7, fiber=3
        # round(200/50 + 7/12 - 3/5) = round(4.0 + 0.583 - 0.6) = round(3.983) = 4
        assert ww["value"] == 4

    def test_single_item_both_modes_equal(self):
        """For a single item, per_item and total should give the same result."""
        food = _mock_food("Food", food_nutrients=[
            _mock_food_nutrient("Energy", 150),
            _mock_food_nutrient("Total lipid (fat)", 5),
            _mock_food_nutrient("Fiber, total dietary", 3),
        ])
        config = [_mock_config_item("WW", "points", formula="round(calories/50 + fat/12 - fiber/5)")]
        items = [_make_input(food)]
        r_per = NutrientCalculator.compute_summary(items, config, formula_mode="per_item")
        r_tot = NutrientCalculator.compute_summary(items, config, formula_mode="total")
        assert r_per[0]["value"] == r_tot[0]["value"]


# ── Multiple Items (Daily Summary) ───────────────────────


class TestMultipleItems:
    """Summing nutrients across multiple foods."""

    def test_calories_sum_across_foods(self):
        """Total calories should be sum of individual foods."""
        food1 = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy (Atwater General Factors)", 60),
        ])
        food2 = _mock_food("Bread", food_nutrients=[
            _mock_food_nutrient("Energy", 265),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary(
            [_make_input(food1, quantity=238, unit="grams"),
             _make_input(food2, quantity=50, unit="grams")],
            config,
        )
        cal = next(r for r in result if r["name"] == "Calories")
        # Apple: 60 * 238/100 = 142.8
        # Bread: 265 * 50/100 = 132.5
        # Total: 275.3
        assert abs(cal["value"] - 275.3) < 1

    def test_mixed_energy_types_coalesced_per_food(self):
        """Foods with different energy nutrient types should all contribute correctly."""
        # USDA food with Atwater only (no plain Energy)
        food1 = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy (Atwater General Factors)", 60, nutrient_id=199),
            _mock_food_nutrient("Energy (Atwater Specific Factors)", 54, nutrient_id=200),
        ])
        # Custom food with plain Energy only
        food2 = _mock_food("Protein Shake", serving_size=325, created_by_user_id=1, food_nutrients=[
            _mock_food_nutrient("Energy", 140),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary(
            [_make_input(food1, quantity=100, unit="grams"),
             _make_input(food2, quantity=325, unit="grams")],
            config,
        )
        cal = next(r for r in result if r["name"] == "Calories")
        # Apple: Atwater General 60 * 100/100 = 60
        # Shake: 140 * 325/325 = 140
        # Total: 200
        assert abs(cal["value"] - 200) < 1


# ── Standard Nutrient Config (no formula) ─────────────────


class TestStandardNutrients:
    """Config items with nutrient_id (no formula) should sum the matching nutrient."""

    def test_protein_by_nutrient_id(self):
        """Protein config with nutrient_id should find and sum protein values."""
        prot_id = 42
        food = _mock_food("Chicken", food_nutrients=[
            _mock_food_nutrient("Protein", 31, nutrient_id=prot_id),
            _mock_food_nutrient("Energy", 165),
        ])
        config = [_mock_config_item("Protein", "g", nutrient_id=prot_id)]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        prot = next(r for r in result if r["name"] == "Protein")
        assert abs(prot["value"] - 31) < 1

    def test_nutrient_id_not_found_returns_zero(self):
        """If configured nutrient_id doesn't exist on any food, return 0."""
        food = _mock_food("Salt", food_nutrients=[
            _mock_food_nutrient("Sodium, Na", 38758),
        ])
        config = [_mock_config_item("Protein", "g", nutrient_id=999)]
        result = NutrientCalculator.compute_summary([_make_input(food)], config)
        prot = next(r for r in result if r["name"] == "Protein")
        assert prot["value"] == 0


# ── Edge Cases ────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and empty inputs."""

    def test_empty_items_returns_zeros(self):
        """No items should return config metrics with zero values."""
        config = [
            _mock_config_item("Calories", "kcal", formula="calories"),
            _mock_config_item("Protein", "g", nutrient_id=42),
        ]
        result = NutrientCalculator.compute_summary([], config)
        assert len(result) == 2
        assert all(r["value"] == 0 for r in result)

    def test_empty_config_returns_empty(self):
        """No config items should return empty list."""
        food = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy", 52),
        ])
        result = NutrientCalculator.compute_summary([_make_input(food)], [])
        assert result == []

    def test_zero_quantity_returns_zeros(self):
        """Zero quantity should return zeros."""
        food = _mock_food("Apple", food_nutrients=[
            _mock_food_nutrient("Energy", 52),
        ])
        config = [_mock_config_item("Calories", "kcal", formula="calories")]
        result = NutrientCalculator.compute_summary([_make_input(food, quantity=0)], config)
        cal = next(r for r in result if r["name"] == "Calories")
        assert cal["value"] == 0
