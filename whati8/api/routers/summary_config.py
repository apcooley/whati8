"""
API endpoints for user summary bar configuration.

CRUD for which nutrients/metrics appear in the daily summary bar,
including ordering, custom names, and formula-based custom metrics.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.api.deps import get_current_user, get_db
from whati8.models import User
from whati8.models.user_summary_nutrient import UserSummaryNutrient
from whati8.models.nutrient import Nutrient
from whati8.services.formula_engine import FRIENDLY_TO_USDA, evaluate_formula

router = APIRouter(prefix="/summary-config", tags=["Summary Config"])


class SummaryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nutrient_id: int | None
    display_name: str
    display_unit: str
    display_order: int
    formula: str | None = None


class SummaryItemCreate(BaseModel):
    nutrient_id: int | None = None
    display_name: str = Field(..., max_length=50)
    display_unit: str = Field("", max_length=20)
    formula: str | None = None


class SummaryItemUpdate(BaseModel):
    display_name: str | None = None
    display_unit: str | None = None
    formula: str | None = None


class ReorderRequest(BaseModel):
    item_ids: list[int] = Field(..., description="Ordered list of summary item IDs")


# Default summary nutrients for new users
DEFAULT_SUMMARY = [
    ("Calories", "kcal", "energy"),
    ("Protein", "g", "protein"),
    ("Carbs", "g", "carbohydrate, by difference"),
    ("Fat", "g", "total lipid (fat)"),
    ("Fiber", "g", "fiber, total dietary"),
]


async def _ensure_defaults(db: AsyncSession, user_id: int) -> list[UserSummaryNutrient]:
    """Create default summary config if user has none."""
    result = await db.execute(
        select(UserSummaryNutrient)
        .where(UserSummaryNutrient.user_id == user_id)
        .options(selectinload(UserSummaryNutrient.nutrient))
        .order_by(UserSummaryNutrient.display_order)
    )
    items = list(result.scalars().all())
    if items:
        return items

    # Create defaults
    for i, (name, unit, usda_name) in enumerate(DEFAULT_SUMMARY):
        # Find nutrient by name
        nut_result = await db.execute(
            select(Nutrient).where(Nutrient.name.ilike(f"%{usda_name}%"))
        )
        nutrients = list(nut_result.scalars().all())
        nutrient = None
        for n in nutrients:
            if usda_name == "energy":
                # Prefer kJ Energy (id=39 in production) — most foods have it.
                # Fall back to kcal Energy for test databases or other schemas.
                if n.name.lower() == "energy" and n.unit == "kJ":
                    nutrient = n
                    break
                elif n.name.lower() == "energy" and n.unit == "kcal":
                    nutrient = (
                        n  # keep looking for kJ version, but accept kcal as fallback
                    )
            elif n.name.lower() == usda_name:
                nutrient = n
                break

        item = UserSummaryNutrient(
            user_id=user_id,
            nutrient_id=nutrient.id if nutrient else None,
            display_name=name,
            display_unit=unit,
            display_order=i,
        )
        db.add(item)

    await db.commit()

    # Re-fetch
    result = await db.execute(
        select(UserSummaryNutrient)
        .where(UserSummaryNutrient.user_id == user_id)
        .options(selectinload(UserSummaryNutrient.nutrient))
        .order_by(UserSummaryNutrient.display_order)
    )
    return list(result.scalars().all())


def _to_response(item: UserSummaryNutrient) -> SummaryItemResponse:
    return SummaryItemResponse(
        id=item.id,
        nutrient_id=item.nutrient_id,
        display_name=item.display_name
        or (item.nutrient.name if item.nutrient else "Unknown"),
        display_unit=item.display_unit or (item.nutrient.unit if item.nutrient else ""),
        display_order=item.display_order,
        formula=item.formula,
    )


@router.get("", response_model=list[SummaryItemResponse])
async def list_summary_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's summary bar configuration (creates defaults if empty)."""
    items = await _ensure_defaults(db, current_user.id)
    return [_to_response(item) for item in items]


@router.post("", response_model=SummaryItemResponse, status_code=201)
async def add_summary_item(
    data: SummaryItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a new metric to the summary bar."""
    # Validate formula if provided
    if data.formula:
        test_values = {k: 100.0 for k in FRIENDLY_TO_USDA}
        result = evaluate_formula(data.formula, test_values)
        if result is None:
            raise HTTPException(400, "Invalid formula expression")

    # Get max order
    result = await db.execute(
        select(UserSummaryNutrient.display_order)
        .where(UserSummaryNutrient.user_id == current_user.id)
        .order_by(UserSummaryNutrient.display_order.desc())
        .limit(1)
    )
    max_order = result.scalar() or 0

    item = UserSummaryNutrient(
        user_id=current_user.id,
        nutrient_id=data.nutrient_id,
        display_name=data.display_name,
        display_unit=data.display_unit,
        display_order=max_order + 1,
        formula=data.formula,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Load nutrient relationship
    result = await db.execute(
        select(UserSummaryNutrient)
        .where(UserSummaryNutrient.id == item.id)
        .options(selectinload(UserSummaryNutrient.nutrient))
    )
    item = result.scalar_one()
    return _to_response(item)


@router.put("/reorder", response_model=list[SummaryItemResponse])
async def reorder_summary(
    data: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reorder summary items by providing ordered list of IDs."""
    result = await db.execute(
        select(UserSummaryNutrient)
        .where(UserSummaryNutrient.user_id == current_user.id)
        .options(selectinload(UserSummaryNutrient.nutrient))
    )
    items = {item.id: item for item in result.scalars().all()}

    for order, item_id in enumerate(data.item_ids):
        if item_id in items:
            items[item_id].display_order = order

    await db.commit()

    # Return in new order
    sorted_items = sorted(items.values(), key=lambda x: x.display_order)
    return [_to_response(item) for item in sorted_items]


@router.put("/{item_id}", response_model=SummaryItemResponse)
async def update_summary_item(
    item_id: int,
    data: SummaryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a summary metric."""
    result = await db.execute(
        select(UserSummaryNutrient)
        .where(
            UserSummaryNutrient.id == item_id,
            UserSummaryNutrient.user_id == current_user.id,
        )
        .options(selectinload(UserSummaryNutrient.nutrient))
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Summary item not found")

    if data.display_name is not None:
        item.display_name = data.display_name
    if data.display_unit is not None:
        item.display_unit = data.display_unit
    if data.formula is not None:
        if data.formula:
            test_values = {k: 100.0 for k in FRIENDLY_TO_USDA}
            result_val = evaluate_formula(data.formula, test_values)
            if result_val is None:
                raise HTTPException(400, "Invalid formula expression")
        item.formula = data.formula or None

    await db.commit()
    await db.refresh(item)
    return _to_response(item)


@router.delete("/{item_id}", status_code=204)
async def delete_summary_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a metric from the summary bar."""
    result = await db.execute(
        select(UserSummaryNutrient).where(
            UserSummaryNutrient.id == item_id,
            UserSummaryNutrient.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Summary item not found")
    await db.delete(item)
    await db.commit()


@router.get("/available-nutrients", response_model=list[dict])
async def list_available_nutrients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available nutrients for adding to summary."""
    from whati8.services.formula_engine import get_friendly_name

    result = await db.execute(select(Nutrient).order_by(Nutrient.name))
    nutrients = result.scalars().all()
    out = []
    for n in nutrients:
        friendly, unit = get_friendly_name(n.name)
        out.append(
            {
                "nutrient_id": n.id,
                "name": n.name,
                "friendly_name": friendly,
                "unit": unit or n.unit,
            }
        )
    return out
