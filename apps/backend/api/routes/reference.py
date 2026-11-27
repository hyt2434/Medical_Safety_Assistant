"""Authenticated, read-only access to imported reference data."""
from fastapi import APIRouter, Depends, Query, HTTPException
import os
import psycopg
from psycopg.rows import dict_row
from apps.backend.api.deps import current_session
from shared.auth.settings import core_database_dsn

router = APIRouter(prefix="/api/reference", tags=["Reference data"])

@router.get("/medication-spelling")
def medication_spelling(q: str = Query(min_length=1, max_length=120),
                        strength: str = Query(default="", max_length=120),
                        _session=Depends(current_session)):
    from apps.backend.api.medication_spelling import catalog_rows, suggestions
    try:
        rows = catalog_rows()
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "Chưa tải được danh mục gợi ý tên thuốc")
    return {"suggestions": suggestions(q, strength, rows),
            "source": "Danh mục cục bộ · chưa thay thế đối chiếu toa gốc"}

@router.get("/medications")
def medications(q: str = Query(default="", max_length=120), _session=Depends(current_session)):
    dsn, build = core_database_dsn(), os.environ.get('CORE_REFERENCE_BUILD')
    if not dsn or not build:
        raise HTTPException(503, "Chưa cấu hình danh mục Core V4")
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    try:
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            counts = {table: connection.execute(
                f'SELECT count(*) AS n FROM msa_ref.{table} WHERE dataset_build=%s', (build,)
            ).fetchone()['n'] for table in ('medications', 'ddinter_mappings')}
            rows = connection.execute('''SELECT id, dataset_build, source_medication_id, brand_name, dosage_form,
                manufacturer, product_details->>'registration_token' AS registration_token,
                (SELECT coalesce(jsonb_agg(jsonb_build_object('ingredient_text_raw',c.ingredient_text_raw,
                    'ingredient_name_raw',c.ingredient_name_raw) ORDER BY c.ordinal),'[]'::jsonb)
                 FROM msa_ref.medication_ingredients c WHERE c.medication_id=m.id AND c.dataset_build=m.dataset_build) AS components
                FROM msa_ref.medications m WHERE dataset_build=%s AND brand_name ILIKE %s
                ORDER BY brand_name, source_medication_id LIMIT 50''', (build, pattern)).fetchall()
    except psycopg.Error:
        raise HTTPException(503, "Danh mục Core hiện chưa sẵn sàng") from None
    return {"source": "PostgreSQL · Core V4", "dataset_build": build, "counts": counts, "medications": rows}
