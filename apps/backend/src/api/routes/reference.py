"""Authenticated, read-only access to imported reference data."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text, inspect
from api.deps import current_session
from auth.db import engine

router = APIRouter(prefix="/api/reference", tags=["Reference data"])

@router.get("/medication-spelling")
def medication_spelling(q: str = Query(min_length=1, max_length=120),
                        strength: str = Query(default="", max_length=120),
                        _session=Depends(current_session)):
    from api.medication_spelling import catalog_rows, suggestions
    try:
        rows = catalog_rows()
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "Chưa tải được danh mục gợi ý tên thuốc")
    return {"suggestions": suggestions(q, strength, rows),
            "source": "Danh mục cục bộ · chưa thay thế đối chiếu toa gốc"}

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
