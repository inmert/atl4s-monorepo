"""Shared validators."""

from fastapi import HTTPException


def safe_bag_name(name: str) -> str:
    if not name or '/' in name or name in ('.', '..'):
        raise HTTPException(400, 'invalid bag name')
    return name
