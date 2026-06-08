"""Shared dependencies and utilities for API routers."""

from beanie import PydanticObjectId
from fastapi import HTTPException


def parse_obj_id(id_str: str, detail: str = "Invalid ID format") -> PydanticObjectId:
    """Parse a string ID into PydanticObjectId, raising HTTPException on failure."""
    try:
        return PydanticObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail=detail)