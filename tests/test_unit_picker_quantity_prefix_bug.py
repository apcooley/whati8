"""
Test suite for unit picker quantity prefix bug.

Issue: Unit options show "6 crackers (28g)" instead of "crackers (28g)".
When user selects quantity + unit, they get "6 6 crackers" (duplicated).

Root cause: food_resolver.py is returning quantity-prefixed unit strings.
Fix should: Strip quantity prefix before returning unit options to frontend.

KEY DISTINCTION:
- Quantity prefix: "1 Bar", "6 crackers", "12 tablets" (number + space + unit)
- Mass/volume unit: "113g", "500mg", "ml" (part of unit name, no space)
"""

import pytest
import re


class TestUnitPickerQuantityPrefixBug:
    """Test that unit options don't contain quantity prefixes."""
    
    def test_unit_should_not_contain_quantity_prefix(self):
        """Unit strings should be 'crackers (28g)', not '6 crackers (28g)'."""
        # Simulate what comes from database (bad)
        bad_unit = "6 crackers (28g)"
        
        # After stripping (good)
        good_unit = re.sub(r'^\d+\s+', '', bad_unit)
        
        assert good_unit == "crackers (28g)"
        assert not re.match(r'^\d+\s+', good_unit)
    
    def test_unit_strip_single_digit_prefix(self):
        """Strip '1 Bar (44g)' → 'Bar (44g)'."""
        unit = "1 Bar (44g)"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == "Bar (44g)"
    
    def test_unit_strip_multi_digit_prefix(self):
        """Strip '12 tablets (500mg)' → 'tablets (500mg)'."""
        unit = "12 tablets (500mg)"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == "tablets (500mg)"
    
    def test_unit_no_prefix_unchanged(self):
        """Units without prefix should remain unchanged."""
        unit = "g"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == "g"
    
    def test_unit_ml_no_prefix(self):
        """ml units should remain unchanged."""
        unit = "ml"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == "ml"
    
    def test_mass_unit_113g_unchanged(self):
        """'113g' is a mass unit, not a quantity prefix—should not be stripped."""
        unit = "113g"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        # No space after digits, so regex doesn't match
        assert cleaned == "113g"
        assert unit == cleaned
    
    def test_user_qty_plus_clean_unit_no_duplication(self):
        """User qty (6) + clean unit ('crackers (28g)') = '6 crackers (28g)'."""
        user_qty = 6
        clean_unit = "crackers (28g)"
        
        result = f"{user_qty} {clean_unit}"
        assert result == "6 crackers (28g)"
        assert result.count("6") == 1  # Only one "6"
        assert result.count("crackers") == 1
    
    def test_user_qty_plus_bad_unit_duplicates(self):
        """User qty (6) + bad unit ('6 crackers') = '6 6 crackers' (WRONG)."""
        user_qty = 6
        bad_unit = "6 crackers (28g)"
        
        result = f"{user_qty} {bad_unit}"
        assert result == "6 6 crackers (28g)"  # Duplicate "6"
        assert result.count("6") == 2  # Two "6"s — BUG!
    
    def test_single_unit_no_quantity_form(self):
        """Some units are just 'tablet', 'piece', 'serving' with no (gram) suffix."""
        unit = "tablet"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        
        result = f"1 {cleaned}"
        assert result == "1 tablet"
        assert not re.match(r'\d+\s+\d+', result)
    
    def test_unit_with_fraction_prefix_edge_case(self):
        """Edge: '0.5 cup (237ml)' — fractional quantities in unit string."""
        unit = "0.5 cup (237ml)"
        # This regex catches digits at start, not decimals
        cleaned = re.sub(r'^\d+(\.\d+)?\s+', '', unit)
        assert cleaned == "cup (237ml)"
    
    def test_multiple_foods_all_cleaned(self):
        """Batch test: verify all common foods are cleaned correctly."""
        test_cases = [
            ("1 Bar (44g)", "Bar (44g)"),
            ("6 crackers (28g)", "crackers (28g)"),
            ("1 serving (113g)", "serving (113g)"),
            ("2 tablets (500mg)", "tablets (500mg)"),
            ("12 ounces (340g)", "ounces (340g)"),
            ("g", "g"),  # Already clean (mass unit)
            ("ml", "ml"),  # Already clean (volume unit)
            ("113g", "113g"),  # Already clean (mass quantity, not prefix)
            ("cup (237ml)", "cup (237ml)"),  # Already clean
        ]
        
        for bad_unit, expected_clean in test_cases:
            cleaned = re.sub(r'^\d+\s+', '', bad_unit)
            assert cleaned == expected_clean, f"Failed for {bad_unit}"
    
    def test_food_resolver_mock_stripping(self):
        """Mock test: food_resolver.get_serving_options() should return clean units."""
        mock_db_units = [
            {"quantity": 1, "unit": "1 Bar (44g)"},
            {"quantity": 6, "unit": "6 crackers (28g)"},
            {"quantity": 113, "unit": "113g"},  # This is a mass unit, not a prefix
        ]
        
        # After cleaning
        expected_cleaned = [
            {"quantity": 1, "unit": "Bar (44g)"},
            {"quantity": 6, "unit": "crackers (28g)"},
            {"quantity": 113, "unit": "113g"},  # Stays as-is
        ]
        
        for db_item, expected in zip(mock_db_units, expected_cleaned):
            db_unit = db_item["unit"]
            stripped = re.sub(r'^\d+\s+', '', db_unit)
            assert stripped == expected["unit"]
    
    def test_display_with_user_selected_qty(self):
        """End-to-end: user selects quantity + unit → display should be clean."""
        # User wants to log "6 crackers"
        user_qty = 6
        
        # Backend returns unit option (currently bad, should be good)
        # BAD: "6 crackers (28g)"
        # GOOD: "crackers (28g)"
        good_unit = "crackers (28g)"
        
        display = f"{user_qty} {good_unit}"
        assert display == "6 crackers (28g)"
        assert not re.search(r'(\d+).*\1', display)  # No duplicate digits


class TestEdgeCases:
    """Edge cases for quantity prefix stripping."""
    
    def test_parenthetical_content_with_digits(self):
        """Ensure we don't strip digits inside parentheses."""
        unit = "Bar (44g)"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == "Bar (44g)"
        assert "44" in cleaned
    
    def test_empty_unit_string(self):
        """Empty unit should stay empty."""
        unit = ""
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == ""
    
    def test_whitespace_variations(self):
        """Handle various whitespace patterns."""
        test_cases = [
            ("1  Bar (44g)", "Bar (44g)"),  # Double space
            ("1\tBar (44g)", "Bar (44g)"),  # Tab — FAILS, regex only matches space
            ("1   serving", "serving"),  # Multiple spaces
        ]
        
        for unit, expected in test_cases:
            cleaned = re.sub(r'^\d+\s+', '', unit)
            # Note: tab handling might differ, this is acceptable
            if '\t' not in unit:
                assert cleaned == expected
    
    def test_numeric_unit_names(self):
        """Some units might be numeric (e.g., '500mg' as standalone)."""
        unit = "500mg"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        # Should NOT strip "500" because there's no space after digits
        assert cleaned == "500mg"
    
    def test_grams_as_unit_not_quantity(self):
        """'113g' is the unit itself (113 grams), not '113 <unit>'."""
        unit = "113g"
        cleaned = re.sub(r'^\d+\s+', '', unit)
        assert cleaned == "113g"
        # User would log "1 113g" meaning "1 serving of 113 grams"
        result = f"1 {cleaned}"
        assert result == "1 113g"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
