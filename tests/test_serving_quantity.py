"""Tests for serving_quantity on custom food creation and display.

When a food has a multi-unit serving (e.g., "4 slices = 56g"), the system must:
1. portion_description = "slices (14g)" — the unit label, NO quantity prefix
2. amount = 4 — the default quantity when this portion is selected
3. gram_weight = 14 — weight per single unit
4. unit_name = "slices" — the unit
5. Display: "4 slices (14g)" — quantity comes from amount, not baked into the label
"""

import pytest
import psycopg2
import httpx
from datetime import date

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from whati8.config import settings
from whati8.services.daily_log_service import DailyLogService

DB_URL = settings.get_async_database_url()
TEST_USER_ID = 2
SERVER = "http://192.168.1.11:9428"


def _db(sql, params=None):
    conn = psycopg2.connect(dbname="whati8", user="whati8", password="whati8", host="localhost")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql, params or ())
    try:
        rows = cur.fetchall()
    except Exception:
        rows = []
    cur.close()
    conn.close()
    return rows


def _cleanup():
    _db("""
        DELETE FROM food_logs WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST SQ%%');
        DELETE FROM food_nutrients WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST SQ%%');
        DELETE FROM food_portions WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST SQ%%');
        DELETE FROM user_foods WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST SQ%%');
        DELETE FROM foods WHERE name LIKE 'TEST SQ%%';
    """)


def _login():
    resp = httpx.post(f"{SERVER}/auth/login", json={"login": "testbot", "password": "testbot123"})
    return resp.json()["access_token"]


def _create_food(token, **kwargs):
    resp = httpx.post(f"{SERVER}/foods/", json=kwargs, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 201], f"Create failed: {resp.text}"
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════
# PORTION STORAGE: gram_weight, amount, description
# ══════════════════════════════════════════════════════════════════════════


class TestPortionStorage:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        _cleanup()
        yield
        _cleanup()

    def test_multi_unit_gram_weight_is_per_unit(self):
        """4 slices = 56g → gram_weight should be 14g (per slice)."""
        token = _login()
        food = _create_food(token,
            name="TEST SQ Turkey Slices",
            serving_size=56.0, unit="slices", custom_unit="slices",
            serving_quantity=4, gram_weight=56.0,
            calories=70.0, protein=10.0, fat=2.5, carbs=4.0, fiber=0.0,
        )

        rows = _db(
            "SELECT amount, gram_weight, unit_name FROM food_portions WHERE food_id = %s AND unit_name = 'slices'",
            (food["id"],)
        )
        assert len(rows) == 1
        amount, gram_weight, unit_name = rows[0]
        assert abs(float(gram_weight) - 14.0) < 0.1, f"Expected gram_weight=14, got {gram_weight}"
        assert float(amount) == 4.0, f"Expected amount=4, got {amount}"

    def test_multi_unit_description_has_no_quantity_prefix(self):
        """portion_description should be the unit label only, no quantity prefix.
        
        'slices (14g)' NOT '4 slices (56g)' — the quantity is in `amount`, not in the label.
        """
        token = _login()
        food = _create_food(token,
            name="TEST SQ Turkey Desc",
            serving_size=56.0, unit="slices", custom_unit="slices",
            serving_quantity=4, gram_weight=56.0,
            calories=70.0, protein=10.0, fat=2.5, carbs=4.0, fiber=0.0,
        )

        rows = _db(
            "SELECT portion_description FROM food_portions WHERE food_id = %s AND unit_name = 'slices'",
            (food["id"],)
        )
        desc = rows[0][0]
        # Should NOT start with a number — the quantity belongs in `amount`
        assert not desc[0].isdigit(), \
            f"Description should not start with quantity. Got '{desc}'. Quantity goes in `amount` field."
        assert "14g" in desc or "14.0g" in desc, \
            f"Description should show per-unit weight (14g), got '{desc}'"

    def test_single_unit_unchanged(self):
        """serving_quantity=1 → amount=1, gram_weight=serving_size."""
        token = _login()
        food = _create_food(token,
            name="TEST SQ Single Bar",
            serving_size=50.0, unit="bar", custom_unit="bar",
            gram_weight=50.0,
            calories=200.0, protein=20.0, fat=5.0, carbs=25.0, fiber=3.0,
        )

        rows = _db(
            "SELECT amount, gram_weight FROM food_portions WHERE food_id = %s AND unit_name = 'bar'",
            (food["id"],)
        )
        amount, gram_weight = rows[0]
        assert float(amount) == 1.0
        assert abs(float(gram_weight) - 50.0) < 0.1


# ══════════════════════════════════════════════════════════════════════════
# CALORIE CALCULATION
# ══════════════════════════════════════════════════════════════════════════


class TestCalorieCalculation:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        _cleanup()
        yield
        _cleanup()

    @pytest.mark.asyncio
    async def test_one_slice_gives_quarter_calories(self):
        """14g (1 slice) of a 56g/70kcal serving = 17.5 kcal."""
        rows = _db(
            "INSERT INTO foods (name, serving_size, unit, created_by_user_id) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            ("TEST SQ Calorie Check", 56.0, "slices", TEST_USER_ID)
        )
        food_id = rows[0][0]
        _db("INSERT INTO food_nutrients (food_id, nutrient_id, amount_per_serving) VALUES (%s, %s, %s)",
            (food_id, 39, 70.0))
        _db("INSERT INTO food_logs (user_id, food_id, quantity, unit, logged_at) VALUES (%s, %s, %s, %s, %s)",
            (TEST_USER_ID, food_id, 14.0, "g", "2026-03-20 12:00:00"))

        eng = create_async_engine(DB_URL, echo=False, pool_size=1, max_overflow=0)
        Session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with Session() as db:
                result = await DailyLogService.get_daily_logs(db, TEST_USER_ID, date(2026, 3, 20))
        finally:
            await eng.dispose()

        log = None
        for meal in result.get("meals", []):
            for l in meal.get("logs", []):
                if l["food_id"] == food_id: log = l
        if not log:
            for l in result.get("ungrouped_logs", []):
                if l["food_id"] == food_id: log = l

        assert log is not None
        assert abs(log["calories"] - 17.5) < 0.5, f"Expected ~17.5, got {log['calories']}"

    @pytest.mark.asyncio
    async def test_full_serving_gives_full_calories(self):
        """56g (full serving) = 70 kcal."""
        rows = _db(
            "INSERT INTO foods (name, serving_size, unit, created_by_user_id) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            ("TEST SQ Full Serving", 56.0, "slices", TEST_USER_ID)
        )
        food_id = rows[0][0]
        _db("INSERT INTO food_nutrients (food_id, nutrient_id, amount_per_serving) VALUES (%s, %s, %s)",
            (food_id, 39, 70.0))
        _db("INSERT INTO food_logs (user_id, food_id, quantity, unit, logged_at) VALUES (%s, %s, %s, %s, %s)",
            (TEST_USER_ID, food_id, 56.0, "g", "2026-03-20 12:30:00"))

        eng = create_async_engine(DB_URL, echo=False, pool_size=1, max_overflow=0)
        Session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with Session() as db:
                result = await DailyLogService.get_daily_logs(db, TEST_USER_ID, date(2026, 3, 20))
        finally:
            await eng.dispose()

        log = None
        for meal in result.get("meals", []):
            for l in meal.get("logs", []):
                if l["food_id"] == food_id: log = l
        if not log:
            for l in result.get("ungrouped_logs", []):
                if l["food_id"] == food_id: log = l

        assert log is not None
        assert abs(log["calories"] - 70.0) < 0.5, f"Expected ~70, got {log['calories']}"


# ══════════════════════════════════════════════════════════════════════════
# FRONTEND CONTRACTS
# ══════════════════════════════════════════════════════════════════════════


class TestFrontendContract:

    def test_photo_results_dispatches_default_quantity(self):
        """PhotoResults must include default_quantity in the save dispatch."""
        import re
        with open("frontend/src/lib/components/PhotoResults.svelte") as f:
            source = f.read()

        dispatch_match = re.search(r"dispatch\('save',\s*\{(.*?)\}\s*\)", source, re.DOTALL)
        assert dispatch_match, "Could not find dispatch('save', {...})"
        dispatch_body = dispatch_match.group(1)
        assert "default_quantity" in dispatch_body or "custom_qty" in dispatch_body, \
            f"dispatch must include default_quantity. Got: {dispatch_body[:200]}"

    def test_photo_results_description_no_hardcoded_one(self):
        """Description should not hardcode '1' — use custom_qty."""
        with open("frontend/src/lib/components/PhotoResults.svelte") as f:
            source = f.read()
        assert "desc = `1 ${" not in source, \
            "Description should use custom_qty, not hardcode '1'"

    def test_serving_label_separates_qty_from_unit(self):
        """getServingLabel should compose qty + unit, not return a compound string."""
        from whati8.config import settings  # just to verify we can import
        with open("frontend/src/lib/types/profile.ts") as f:
            source = f.read()
        # The function should NOT have special handling for units starting with digits
        # because unit labels should never start with digits
        assert "test(unit)" not in source or "^\\d" not in source, \
            "getServingLabel should not need to check for digit-prefixed units"
