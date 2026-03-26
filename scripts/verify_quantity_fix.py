#!/usr/bin/env python3
"""
Verification script for duplicate quantity bug fix.

This script simulates the getServingLabel() function behavior
to demonstrate the fix works correctly.
"""

import re
from typing import Optional


def get_serving_label_old(qty: float, unit: str) -> str:
    """Old buggy implementation."""
    return f"{qty} {unit}"


def get_serving_label_new(qty: float, unit: str) -> str:
    """New fixed implementation."""
    # If unit starts with a digit, it already includes quantity
    if unit and re.match(r'^\d', unit):
        return unit
    
    # Format quantity: remove .0 for whole numbers
    qty_str = str(int(qty)) if qty == int(qty) else str(qty)
    
    # Otherwise prepend quantity
    return f"{qty_str} {unit}"


def test_case(qty: float, unit: str, expected: str):
    """Test a single case and print results."""
    old_result = get_serving_label_old(qty, unit)
    new_result = get_serving_label_new(qty, unit)
    
    old_pass = "✅" if old_result == expected else "❌"
    new_pass = "✅" if new_result == expected else "❌"
    
    print(f"\nInput: qty={qty}, unit='{unit}'")
    print(f"  Expected: '{expected}'")
    print(f"  Old {old_pass}: '{old_result}'")
    print(f"  New {new_pass}: '{new_result}'")
    
    return new_result == expected


def main():
    """Run all test cases."""
    print("=" * 60)
    print("Duplicate Quantity Bug Fix Verification")
    print("=" * 60)
    
    test_cases = [
        # (qty, unit, expected)
        (1.0, "1 Bar (44g)", "1 Bar (44g)"),
        (6.0, "6 crackers (28g)", "6 crackers (28g)"),
        (1.0, "113g", "113g"),
        (1.0, "32g", "32g"),
        (1.0, "bottle (325g)", "1 bottle (325g)"),
        (1.0, "roll (43g)", "1 roll (43g)"),
        (4.0, "slices (14g)", "4 slices (14g)"),
        (100.0, "grams", "100 grams"),
        (1.0, "1 Bun (43g)", "1 Bun (43g)"),
        (1.0, "1 Bar (40g)", "1 Bar (40g)"),
        (1.5, "1.5 cups (360g)", "1.5 cups (360g)"),
    ]
    
    passed = 0
    failed = 0
    
    for qty, unit, expected in test_cases:
        if test_case(qty, unit, expected):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 All tests passed! The fix is working correctly.\n")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed. Check the implementation.\n")
        return 1


if __name__ == "__main__":
    exit(main())
