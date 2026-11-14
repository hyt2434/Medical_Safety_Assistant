"""Authenticated, read-only access to imported reference data."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text, inspect
from api.deps import current_session
from auth.db import engine

router = APIRouter(prefix="/api/reference", tags=["Reference data"])

@router.get("/medications")
def medications(q: str = Query(default="", max_length=120), _session=Depends(current_session)):
    db = engine()
    if not inspect(db).has_table("reference_source_rows"):
        raise HTTPException(503, "Nguồn dữ liệu chưa được nạp")
    with db.connect() as connection:
        counts = dict(connection.execute(text("SELECT source, count(*) FROM reference_source_rows GROUP BY source")).all())
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        rows = connection.execute(text("SELECT payload FROM reference_source_rows WHERE source='medications' AND payload->>'brand_name' ILIKE :query ORDER BY ordinal LIMIT 50"), {"query": pattern}).scalars().all()
    return {"source": "PostgreSQL · CSV dự án", "counts": counts, "medications": rows}
