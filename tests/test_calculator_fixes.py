import pytest
from whati8.services.nutrient_calculator import _eval_formula, compute_item_nutrients, NutrientInput

def test_eval_formula_complex():
    values = {"calories": 100, "fat": 10, "fiber": 5, "protein": 10}
    # Test capitalization
    assert _eval_formula("Calories / 2", values) == 50.0
    # Test formula with min and round
    assert _eval_formula("round(Calories/50 + Fat/12 - min(Fiber, 4)/5, 1)", values) == 2.0
    # The formula actually is: 100/50 (2.0) + 10/12 (0.833) - 4/5 (0.8) = 2.033...
    # Round to nearest 1 (unit, not digits) -> round(2.033) = 2
    
    # Test with 0.5 unit
    assert _eval_formula("round(Calories, 0.5)", {"calories": 10.1}) == 10.0
    assert _eval_formula("round(Calories, 0.5)", {"calories": 10.3}) == 10.5
    
    # 100 / 33 = 3.03. round(3.03, 1) should be 3.0 if unit=1, or 3.0 if digits=1.
    # Our round(x, unit) means if unit=1, round to nearest integer.
    assert _eval_formula("round(3.03, 1)", {}) == 3.0
    assert _eval_formula("round(3.5, 1)", {}) == 4.0
    
def test_energy_coalesce_kcal_vs_kj():
    class MockNutrient:
        def __init__(self, name, unit):
            self.name = name
            self.unit = unit
            
    class MockFoodNutrient:
        def __init__(self, name, unit, amount, nid):
            self.nutrient = MockNutrient(name, unit)
            self.amount_per_serving = amount
            self.nutrient_id = nid

    class MockFood:
        def __init__(self, nutrients):
            self.food_nutrients = nutrients
            self.created_by_user_id = None
            self.serving_size = 100
            self.portions = []

    # Case: both kcal and kJ Energy exist. kcal should win.
    f = MockFood([
        MockFoodNutrient("Energy", "kJ", 1000, 1),
        MockFoodNutrient("Energy", "kcal", 239, 2),
    ])
    item = NutrientInput(food=f, quantity=100, unit="g")
    friendly, _ = compute_item_nutrients(item)
    assert friendly["calories"] == 239.0
    
    # Case: only kJ exists. kJ should be used.
    f2 = MockFood([
        MockFoodNutrient("Energy", "kJ", 1000, 1),
    ])
    item2 = NutrientInput(food=f2, quantity=100, unit="g")
    friendly2, _ = compute_item_nutrients(item2)
    assert friendly2["calories"] == 1000.0
    
def test_rounding_in_summary():
    from whati8.services.nutrient_calculator import NutrientCalculator
    
    class MockConfig:
        def __init__(self, name, formula=None, nid=None):
            self.display_name = name
            self.display_unit = "x"
            self.formula = formula
            self.nutrient_id = nid
            
    item_friendly = {"calories": 100.12345}
    item_by_id = {1: 100.12345}
    config = [MockConfig("Test", formula="Calories")]
    
    results = NutrientCalculator.compute_summary_from_precomputed(
        [item_friendly], [item_by_id], config
    )
    assert results[0]["value"] == 100.1
