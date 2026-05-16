"""Account config API endpoints."""

from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId

from trade_alpha.account import (
    create_account_config,
    get_account_config_by_id,
    list_account_configs,
    update_account_config,
    delete_account_config,
)
from trade_alpha.api.schemas import (
    AccountConfigCreateRequest,
    AccountConfigUpdateRequest,
)


def _config_to_dict(c) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "initial_capital": c.initial_capital,
        "buy_fee_rate": c.buy_fee_rate,
        "sell_fee_rate": c.sell_fee_rate,
        "stamp_tax_rate": c.stamp_tax_rate,
        "min_fee": c.min_fee,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


router = APIRouter(prefix="/account-configs", tags=["account-configs"])


@router.get("")
async def get_account_configs():
    """List all account configs."""
    configs = await list_account_configs()
    return [_config_to_dict(c) for c in configs]


@router.get("/{account_config_id}")
async def get_account_config(account_config_id: PydanticObjectId):
    """Get account config by ID."""
    c = await get_account_config_by_id(account_config_id)
    if not c:
        raise HTTPException(status_code=404, detail="Account config not found")
    return _config_to_dict(c)


@router.post("")
async def create_account_config_endpoint(request: AccountConfigCreateRequest):
    """Create a new account config."""
    try:
        c = await create_account_config(
            name=request.name,
            initial_capital=request.initial_capital,
            buy_fee_rate=request.buy_fee_rate,
            sell_fee_rate=request.sell_fee_rate,
            stamp_tax_rate=request.stamp_tax_rate,
            min_fee=request.min_fee,
        )
        return _config_to_dict(c)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{account_config_id}")
async def update_account_config_endpoint(account_config_id: PydanticObjectId, request: AccountConfigUpdateRequest):
    """Update account config."""
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    c = await update_account_config(account_config_id, **update_data)
    if not c:
        raise HTTPException(status_code=404, detail="Account config not found")
    return _config_to_dict(c)


@router.delete("/{account_config_id}")
async def delete_account_config_endpoint(account_config_id: PydanticObjectId):
    """Delete account config."""
    deleted = await delete_account_config(account_config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account config not found")
    return {"message": "Account config deleted"}
