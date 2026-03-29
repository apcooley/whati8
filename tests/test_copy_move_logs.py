"""Tests for copy and move food log operations.

Endpoints:
- POST /logs/{log_id}/copy — duplicate a log to a target date
- PATCH /logs/{log_id}/move — move a log to a different date/meal
- POST /logs/copy-meal — copy all logs from a meal on one date to another
"""

import pytest
import psycopg2
import httpx

SERVER = "http://192.168.1.11:9428"
TEST_USER_ID = 2  # testbot


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


def _login(username="testbot", password="testbot123"):
    resp = httpx.post(f"{SERVER}/auth/login", json={"login": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _cleanup():
    _db("""
        DELETE FROM food_logs WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST CM%%');
        DELETE FROM food_nutrients WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST CM%%');
        DELETE FROM food_portions WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST CM%%');
        DELETE FROM user_foods WHERE food_id IN (SELECT id FROM foods WHERE name LIKE 'TEST CM%%');
        DELETE FROM foods WHERE name LIKE 'TEST CM%%';
    """)


def _create_test_food():
    """Create a test food and return its id."""
    rows = _db(
        "INSERT INTO foods (name, serving_size, unit, created_by_user_id) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        ("TEST CM Food", 100.0, "g", TEST_USER_ID)
    )
    food_id = rows[0][0]
    _db("INSERT INTO food_nutrients (food_id, nutrient_id, amount_per_serving) VALUES (%s, %s, %s)",
        (food_id, 39, 200.0))
    return food_id


def _create_log(food_id, logged_at, meal_id=None, quantity=100.0, unit="g", notes=None):
    """Create a food log directly in DB and return its id."""
    rows = _db(
        "INSERT INTO food_logs (user_id, food_id, meal_id, quantity, unit, logged_at, notes) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (TEST_USER_ID, food_id, meal_id, quantity, unit, logged_at, notes)
    )
    return rows[0][0]


def _get_log(log_id):
    """Get a food log by id."""
    rows = _db("SELECT id, food_id, meal_id, quantity, unit, logged_at, notes FROM food_logs WHERE id = %s", (log_id,))
    return rows[0] if rows else None


def _count_logs_on_date(target_date, food_id=None):
    """Count food logs for test user on a specific date."""
    if food_id:
        rows = _db(
            "SELECT COUNT(*) FROM food_logs WHERE user_id = %s AND DATE(logged_at) = %s AND food_id = %s",
            (TEST_USER_ID, target_date, food_id)
        )
    else:
        rows = _db(
            "SELECT COUNT(*) FROM food_logs WHERE user_id = %s AND DATE(logged_at) = %s",
            (TEST_USER_ID, target_date)
        )
    return rows[0][0]


# ══════════════════════════════════════════════════════════════════════════
# COPY SINGLE LOG
# ══════════════════════════════════════════════════════════════════════════


class TestCopySingleLog:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        _cleanup()
        yield
        _cleanup()

    def test_copy_log_creates_new_entry(self):
        """Copying a log creates a new entry on the target date."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00", meal_id=2, quantity=150.0, unit="g")
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code in [200, 201], f"Copy failed: {resp.text}"
        new_log = resp.json()

        # New log exists on target date
        assert new_log["id"] != log_id
        assert new_log["food_id"] == food_id
        assert new_log["quantity"] == 150.0
        assert "2026-03-22" in new_log["logged_at"]

    def test_copy_preserves_original(self):
        """Original log is unchanged after copy."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 18:30:00", meal_id=1, quantity=200.0, unit="g", notes="dinner")
        token = _login()

        httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )

        original = _get_log(log_id)
        assert original is not None, "Original should still exist"
        assert str(original[5]).startswith("2026-03-20"), "Original date should be unchanged"
        assert float(original[3]) == 200.0

    def test_copy_inherits_meal(self):
        """Copy inherits the original's meal_id when not specified."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00", meal_id=2)  # Lunch
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        new_log = resp.json()
        assert new_log["meal_id"] == 2 or (new_log.get("meal") and new_log["meal"]["id"] == 2)

    def test_copy_with_different_meal(self):
        """Copy can override the meal assignment."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00", meal_id=2)  # Lunch
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2026-03-22", "meal_id": 3},  # Dinner
            headers=_headers(token),
        )
        new_log = resp.json()
        meal_id = new_log.get("meal_id") or (new_log.get("meal", {}) or {}).get("id")
        assert meal_id == 3

    def test_copy_to_future_date(self):
        """Copying to a future date is allowed."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00")
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2027-01-01"},
            headers=_headers(token),
        )
        assert resp.status_code in [200, 201]
        assert "2027-01-01" in resp.json()["logged_at"]

    def test_copy_to_same_date(self):
        """Copying to the same date creates a duplicate (valid use case)."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00")
        token = _login()

        before_count = _count_logs_on_date("2026-03-20", food_id)
        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2026-03-20"},
            headers=_headers(token),
        )
        assert resp.status_code in [200, 201]
        after_count = _count_logs_on_date("2026-03-20", food_id)
        assert after_count == before_count + 1

    def test_copy_nonexistent_log_returns_404(self):
        """Copying a nonexistent log returns 404."""
        token = _login()
        resp = httpx.post(
            f"{SERVER}/logs/999999/copy",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code == 404

    def test_copy_other_users_log_returns_404(self):
        """Cannot copy another user's log."""
        food_id = _create_test_food()
        # Create log as user 1 (aaronsama), try to copy as testbot (user 2)
        rows = _db(
            "INSERT INTO food_logs (user_id, food_id, quantity, unit, logged_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (1, food_id, 100.0, "g", "2026-03-20 12:00:00")  # user_id=1 (aaronsama)
        )
        other_log_id = rows[0][0]
        token = _login()  # logs in as testbot (user_id=2)

        resp = httpx.post(
            f"{SERVER}/logs/{other_log_id}/copy",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code == 404

    def test_copy_preserves_unit_and_notes(self):
        """Copy preserves unit and notes from original."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00", quantity=2.0, unit="slices (14g)", notes="tasty")
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        new_log = resp.json()
        assert new_log["unit"] == "slices (14g)"
        assert new_log["notes"] == "tasty"

    def test_copy_requires_target_date(self):
        """Copy without target_date returns 422."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00")
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/{log_id}/copy",
            json={},
            headers=_headers(token),
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# MOVE SINGLE LOG
# ══════════════════════════════════════════════════════════════════════════


class TestMoveSingleLog:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        _cleanup()
        yield
        _cleanup()

    def test_move_changes_date(self):
        """Moving a log changes its date."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 14:30:00", meal_id=2)
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code == 200, f"Move failed: {resp.text}"
        updated = resp.json()

        # Date changed, time preserved
        assert "2026-03-22" in updated["logged_at"]
        assert "14:30" in updated["logged_at"]

    def test_move_removes_from_source_date(self):
        """After move, no logs exist on the source date for this food."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 14:30:00")
        token = _login()

        httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )

        assert _count_logs_on_date("2026-03-20", food_id) == 0
        assert _count_logs_on_date("2026-03-22", food_id) == 1

    def test_move_changes_meal(self):
        """Moving a log can change its meal."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00", meal_id=2)  # Lunch
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={"meal_id": 3},  # Move to Dinner, same date
            headers=_headers(token),
        )
        assert resp.status_code == 200
        updated = resp.json()
        meal_id = updated.get("meal_id") or (updated.get("meal", {}) or {}).get("id")
        assert meal_id == 3

    def test_move_date_and_meal(self):
        """Move can change both date and meal at once."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00", meal_id=1)  # Breakfast
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={"target_date": "2026-03-25", "meal_id": 4},  # Snack on the 25th
            headers=_headers(token),
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert "2026-03-25" in updated["logged_at"]
        meal_id = updated.get("meal_id") or (updated.get("meal", {}) or {}).get("id")
        assert meal_id == 4

    def test_move_preserves_time_of_day(self):
        """Move preserves the original time-of-day."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 22:45:00")
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert "22:45" in resp.json()["logged_at"]

    def test_move_to_future_allowed(self):
        """Moving to a future date is allowed."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00")
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={"target_date": "2027-06-15"},
            headers=_headers(token),
        )
        assert resp.status_code == 200

    def test_move_nonexistent_returns_404(self):
        """Moving a nonexistent log returns 404."""
        token = _login()
        resp = httpx.patch(
            f"{SERVER}/logs/999999/move",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code == 404

    def test_move_other_users_log_returns_404(self):
        """Cannot move another user's log."""
        food_id = _create_test_food()
        rows = _db(
            "INSERT INTO food_logs (user_id, food_id, quantity, unit, logged_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (1, food_id, 100.0, "g", "2026-03-20 12:00:00")
        )
        other_log_id = rows[0][0]
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{other_log_id}/move",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code == 404

    def test_move_requires_at_least_one_field(self):
        """Move with neither target_date nor meal_id returns 422."""
        food_id = _create_test_food()
        log_id = _create_log(food_id, "2026-03-20 12:00:00")
        token = _login()

        resp = httpx.patch(
            f"{SERVER}/logs/{log_id}/move",
            json={},
            headers=_headers(token),
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# COPY MEAL (BULK)
# ══════════════════════════════════════════════════════════════════════════


class TestCopyMeal:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        _cleanup()
        yield
        _cleanup()

    def test_copy_meal_duplicates_all_entries(self):
        """Copying a meal duplicates all its log entries."""
        food_id = _create_test_food()
        _create_log(food_id, "2026-03-20 12:00:00", meal_id=2, quantity=100.0)
        _create_log(food_id, "2026-03-20 12:15:00", meal_id=2, quantity=50.0, unit="g", notes="side")
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2026-03-20",
                "source_meal_id": 2,
                "target_date": "2026-03-22",
            },
            headers=_headers(token),
        )
        assert resp.status_code in [200, 201], f"Copy-meal failed: {resp.text}"
        new_logs = resp.json()

        assert len(new_logs) == 2, f"Expected 2 copied logs, got {len(new_logs)}"
        quantities = sorted([l["quantity"] for l in new_logs])
        assert quantities == [50.0, 100.0]

    def test_copy_meal_to_different_meal(self):
        """Copy lunch logs to dinner on a different date."""
        food_id = _create_test_food()
        _create_log(food_id, "2026-03-20 12:00:00", meal_id=2)  # Lunch
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2026-03-20",
                "source_meal_id": 2,
                "target_date": "2026-03-22",
                "target_meal_id": 3,  # Dinner
            },
            headers=_headers(token),
        )
        new_logs = resp.json()
        for log in new_logs:
            meal_id = log.get("meal_id") or (log.get("meal", {}) or {}).get("id")
            assert meal_id == 3

    def test_copy_meal_defaults_target_meal(self):
        """When target_meal_id is omitted, defaults to source_meal_id."""
        food_id = _create_test_food()
        _create_log(food_id, "2026-03-20 12:00:00", meal_id=2)
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2026-03-20",
                "source_meal_id": 2,
                "target_date": "2026-03-22",
            },
            headers=_headers(token),
        )
        new_logs = resp.json()
        for log in new_logs:
            meal_id = log.get("meal_id") or (log.get("meal", {}) or {}).get("id")
            assert meal_id == 2

    def test_copy_meal_empty_source_returns_empty(self):
        """Copying from a date/meal with no logs returns empty list, not error."""
        token = _login()
        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2020-01-01",
                "source_meal_id": 1,
                "target_date": "2026-03-22",
            },
            headers=_headers(token),
        )
        assert resp.status_code in [200, 201]
        assert resp.json() == []

    def test_copy_meal_preserves_units_and_notes(self):
        """Bulk copy preserves unit and notes on each entry."""
        food_id = _create_test_food()
        _create_log(food_id, "2026-03-20 12:00:00", meal_id=2, quantity=3.0, unit="slices (14g)", notes="yum")
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2026-03-20",
                "source_meal_id": 2,
                "target_date": "2026-03-22",
            },
            headers=_headers(token),
        )
        new_logs = resp.json()
        assert len(new_logs) == 1
        assert new_logs[0]["unit"] == "slices (14g)"
        assert new_logs[0]["notes"] == "yum"

    def test_copy_meal_only_copies_specified_meal(self):
        """Only logs from the specified meal are copied, not other meals."""
        food_id = _create_test_food()
        _create_log(food_id, "2026-03-20 08:00:00", meal_id=1, quantity=100.0)  # Breakfast
        _create_log(food_id, "2026-03-20 12:00:00", meal_id=2, quantity=200.0)  # Lunch
        _create_log(food_id, "2026-03-20 18:00:00", meal_id=3, quantity=300.0)  # Dinner
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2026-03-20",
                "source_meal_id": 2,  # Only lunch
                "target_date": "2026-03-22",
            },
            headers=_headers(token),
        )
        new_logs = resp.json()
        assert len(new_logs) == 1
        assert new_logs[0]["quantity"] == 200.0

    def test_copy_meal_does_not_copy_other_users_logs(self):
        """Bulk copy only copies the authenticated user's logs."""
        food_id = _create_test_food()
        # Create a log as user 1 on the same date/meal
        _db(
            "INSERT INTO food_logs (user_id, food_id, meal_id, quantity, unit, logged_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (1, food_id, 2, 999.0, "g", "2026-03-20 12:00:00")
        )
        # Create a log as testbot (user 2)
        _create_log(food_id, "2026-03-20 12:00:00", meal_id=2, quantity=100.0)
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={
                "source_date": "2026-03-20",
                "source_meal_id": 2,
                "target_date": "2026-03-22",
            },
            headers=_headers(token),
        )
        new_logs = resp.json()
        assert len(new_logs) == 1
        assert new_logs[0]["quantity"] == 100.0  # testbot's log, not aaronsama's 999

    def test_copy_meal_requires_source_fields(self):
        """Missing source_date or source_meal_id returns 422."""
        token = _login()

        resp = httpx.post(
            f"{SERVER}/logs/copy-meal",
            json={"target_date": "2026-03-22"},
            headers=_headers(token),
        )
        assert resp.status_code == 422
