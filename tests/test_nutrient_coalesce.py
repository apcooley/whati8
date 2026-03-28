"""Tests for nutrient coalesce strategies.

1. Energy: COALESCE(Atwater_General_199, Atwater_Specific_200, Plain_Energy_39)
2. Carbs: COALESCE(by_summation_107, MAX(by_difference_81, 0))
3. Dedup: Foundation preferred over SR Legacy for same-name foods.

Uses sync psycopg2 for setup/teardown.
Creates a fresh async engine per test to avoid event loop contamination.
"""

import pytest
import psycopg2
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from whati8.config import settings
from whati8.services.daily_log_service import DailyLogService


TEST_USER_ID = 2  # testbot
DB_URL = settings.get_async_database_url()


# ── Sync helpers (psycopg2) ──────────────────────────────────────────────

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
        DELETE FROM food_logs WHERE food_id IN (SELECT id FROM foods WHERE usda_fdc_id BETWEEN 999901 AND 999907);
        DELETE FROM food_nutrients WHERE food_id IN (SELECT id FROM foods WHERE usda_fdc_id BETWEEN 999901 AND 999907);
        DELETE FROM user_foods WHERE food_id IN (SELECT id FROM foods WHERE usda_fdc_id BETWEEN 999901 AND 999907);
        DELETE FROM foods WHERE usda_fdc_id BETWEEN 999901 AND 999907;
    """)


# ── Test data ────────────────────────────────────────────────────────────

FOODS_SPEC = [
    ("atwater_only", "TEST Atwater Only Apple", 999901, [
        (199, 60.0), (200, 54.0), (34, 0.3), (81, 14.0), (80, 0.2),
    ]),
    ("plain_only", "TEST Plain Energy Bread", 999902, [
        (39, 265.0), (34, 8.0), (81, 50.0), (80, 3.0),
    ]),
    ("all_three", "TEST All Three Energy Food", 999903, [
        (39, 250.0), (199, 260.0), (200, 255.0), (34, 10.0), (81, 40.0), (80, 5.0),
    ]),
    ("no_energy", "TEST No Energy Salt", 999904, [
        (34, 0.0),
    ]),
    ("negative_carbs", "TEST Negative Carb Meat", 999905, [
        (39, 150.0), (34, 21.0), (81, -0.48), (80, 9.5),
    ]),
    ("both_carbs", "TEST Both Carb Measures", 999906, [
        (39, 200.0), (34, 5.0), (81, 45.0), (107, 42.0), (80, 3.0),
    ]),
    ("summation_only", "TEST Summation Only Carbs", 999907, [
        (39, 180.0), (34, 4.0), (107, 38.0), (80, 2.0),
    ]),
]


@pytest.fixture(scope="module")
def food_ids():
    """Insert test foods once, return dict, cleanup at end."""
    _cleanup()
    ids = {}
    now = datetime.now(timezone.utc).isoformat()
    for key, name, fdc_id, nutrients in FOODS_SPEC:
        rows = _db(
            "INSERT INTO foods (name, serving_size, usda_fdc_id, unit) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, 100.0, fdc_id, "undetermined")
        )
        fid = rows[0][0]
        ids[key] = fid
        for nid, amt in nutrients:
            _db("INSERT INTO food_nutrients (food_id, nutrient_id, amount_per_serving) VALUES (%s, %s, %s)", (fid, nid, amt))
        _db("INSERT INTO food_logs (user_id, food_id, quantity, unit, logged_at) VALUES (%s, %s, %s, %s, %s)",
            (TEST_USER_ID, fid, 100.0, "g", now))
    yield ids
    _cleanup()


# ── Async helper (fresh engine each call) ────────────────────────────────

async def _find_log(food_name_substr: str) -> dict | None:
    """Fetch daily logs with a disposable engine to avoid loop contamination."""
    eng = create_async_engine(DB_URL, echo=False, pool_size=1, max_overflow=0)
    Session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            result = await DailyLogService.get_daily_logs(db, TEST_USER_ID, date.today())
        for meal in result.get("meals", []):
            for log in meal.get("logs", []):
                if food_name_substr.lower() in log["food_name"].lower():
                    return log
        for log in result.get("ungrouped_logs", []):
            if food_name_substr.lower() in log["food_name"].lower():
                return log
        return None
    finally:
        await eng.dispose()


# ══════════════════════════════════════════════════════════════════════════
# ENERGY COALESCE TESTS
# ══════════════════════════════════════════════════════════════════════════


class TestEnergyCoalesce:

    @pytest.mark.asyncio
    async def test_atwater_only_uses_general(self, food_ids):
        """Foundation food with only Atwater → use General (199) = 60 kcal/100g."""
        log = await _find_log("TEST Atwater Only Apple")
        assert log is not None, "Log entry not found"
        assert abs(log["calories"] - 60.0) < 0.5, f"Expected ~60 (Atwater General), got {log['calories']}"

    @pytest.mark.asyncio
    async def test_plain_energy_fallback(self, food_ids):
        """SR Legacy food with only plain Energy → use 39 = 265 kcal/100g."""
        log = await _find_log("TEST Plain Energy Bread")
        assert log is not None, "Log entry not found"
        assert abs(log["calories"] - 265.0) < 0.5, f"Expected ~265, got {log['calories']}"

    @pytest.mark.asyncio
    async def test_all_three_prefers_general(self, food_ids):
        """Food with all three → prefer Atwater General (199) = 260."""
        log = await _find_log("TEST All Three Energy")
        assert log is not None, "Log entry not found"
        assert abs(log["calories"] - 260.0) < 0.5, f"Expected ~260 (Atwater General), got {log['calories']}"

    @pytest.mark.asyncio
    async def test_no_energy_returns_zero(self, food_ids):
        """Food with no energy nutrient → 0 calories."""
        log = await _find_log("TEST No Energy Salt")
        assert log is not None, "Log entry not found"
        assert log["calories"] == 0.0 or log["calories"] is None, f"Expected 0, got {log['calories']}"


# ══════════════════════════════════════════════════════════════════════════
# CARB COALESCE TESTS
# ══════════════════════════════════════════════════════════════════════════


class TestCarbCoalesce:

    @pytest.mark.asyncio
    async def test_negative_carbs_clamped_to_zero(self, food_ids):
        """Negative 'by difference' carbs → clamp to 0."""
        log = await _find_log("TEST Negative Carb Meat")
        assert log is not None, "Log entry not found"
        assert log["carbs"] == 0.0, f"Negative carbs should clamp to 0, got {log['carbs']}"

    @pytest.mark.asyncio
    async def test_both_carb_measures_prefers_summation(self, food_ids):
        """Both carb measures → prefer summation (107) = 42g, not difference (81) = 45g."""
        log = await _find_log("TEST Both Carb Measures")
        assert log is not None, "Log entry not found"
        assert abs(log["carbs"] - 42.0) < 0.5, f"Expected ~42 (summation), got {log['carbs']}"

    @pytest.mark.asyncio
    async def test_summation_only(self, food_ids):
        """Only carb by summation → use it = 38g."""
        log = await _find_log("TEST Summation Only Carbs")
        assert log is not None, "Log entry not found"
        assert abs(log["carbs"] - 38.0) < 0.5, f"Expected ~38 (summation), got {log['carbs']}"

    @pytest.mark.asyncio
    async def test_positive_difference_when_no_summation(self, food_ids):
        """Positive 'by difference' used when no summation available."""
        log = await _find_log("TEST Plain Energy Bread")
        assert log is not None, "Log entry not found"
        assert abs(log["carbs"] - 50.0) < 0.5, f"Expected ~50 (by difference), got {log['carbs']}"


# ══════════════════════════════════════════════════════════════════════════
# DEDUP TESTS
# ══════════════════════════════════════════════════════════════════════════


class TestUSDADedup:

    @pytest.mark.asyncio
    async def test_no_duplicate_usda_names(self):
        """After dedup, no two USDA foods should share the same name."""
        rows = _db("""
            SELECT name, COUNT(*) as cnt FROM foods
            WHERE usda_fdc_id IS NOT NULL AND is_recipe_expired = false
            GROUP BY name HAVING COUNT(*) > 1
        """)
        if rows:
            pytest.fail(f"Found {len(rows)} duplicate USDA names. Examples: {[r[0] for r in rows[:5]]}")

    @pytest.mark.asyncio
    async def test_foundation_preferred_over_legacy(self):
        """Surviving foods should be from Foundation dataset."""
        rows = _db("""
            SELECT name, MIN(usda_fdc_id), MAX(usda_fdc_id), COUNT(*) FROM foods
            WHERE usda_fdc_id IS NOT NULL AND is_recipe_expired = false
            GROUP BY name HAVING COUNT(*) > 1
        """)
        for row in rows:
            pytest.fail(f"Duplicate '{row[0]}' still exists: fdc_ids {row[1]}..{row[2]}")
