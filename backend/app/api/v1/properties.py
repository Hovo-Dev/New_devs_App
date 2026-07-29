from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from sqlalchemy import text
from app.core.auth import authenticate_request as get_current_user
from app.core.database_pool import DatabasePool

router = APIRouter()


@router.get("/properties")
async def get_properties(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Returns the properties belonging to the authenticated user's tenant only."""
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")

    db_pool = DatabasePool()
    await db_pool.initialize()

    if not db_pool.session_factory:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.get_session() as session:
        result = await session.execute(
            text("SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id ORDER BY id"),
            {"tenant_id": tenant_id},
        )
        rows = result.fetchall()

    items = [{"id": row.id, "name": row.name, "timezone": row.timezone} for row in rows]
    return {"items": items, "total": len(items)}
