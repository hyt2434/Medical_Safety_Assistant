-- Existing local V4 inspection only. No migrations, fixtures or data writes.
-- Run the whole file in one connection. ROLLBACK if a previous transaction failed.
BEGIN TRANSACTION READ ONLY;

-- 1. Connection and server identity.
SELECT current_database() AS database_name, current_user AS username,
       inet_server_addr() AS host, inet_server_port() AS port,
       current_setting('server_version') AS server_version,
       current_setting('data_directory') AS data_directory,
       current_setting('transaction_read_only') AS transaction_read_only;

-- 2. Every expected Core table: 20 OK rows, 193 columns in total.
WITH expected(schema_name, table_name) AS (VALUES
 ('msa_ref','medications'), ('msa_ref','ingredients'),
 ('msa_ref','medication_ingredients'), ('msa_ref','ddinter_mappings'),
 ('msa','conversation_sessions'), ('msa','conversation_messages'),
 ('msa','workflow_instances'), ('msa','intake_sessions'),
 ('msa','intake_inputs'), ('msa','intake_extractions'), ('msa','intake_items'),
 ('msa','medication_entry_versions'), ('msa','entry_matches'),
 ('msa','medication_list_snapshots'), ('msa','snapshot_entries'),
 ('msa','safety_assessments'), ('msa','safety_findings'), ('msa','finding_entries'),
 ('msa','patient_health_sources'), ('msa','patient_health_summaries')
), actual AS (
 SELECT table_schema AS schema_name, table_name
 FROM information_schema.tables
 WHERE table_schema IN ('msa','msa_ref') AND table_type='BASE TABLE'
)
SELECT coalesce(e.schema_name,a.schema_name) AS schema_name,
       coalesce(e.table_name,a.table_name) AS table_name,
       CASE WHEN e.table_name IS NULL THEN 'UNEXPECTED'
            WHEN a.table_name IS NULL THEN 'MISSING' ELSE 'OK' END AS status,
       (SELECT count(*) FROM information_schema.columns c
        WHERE c.table_schema=a.schema_name AND c.table_name=a.table_name) AS columns
FROM expected e FULL JOIN actual a USING (schema_name,table_name)
ORDER BY 1,2;

-- 3. Schema totals. identity.users is an external dependency, not a Core table.
SELECT table_schema, count(*) AS tables
FROM information_schema.tables
WHERE table_schema IN ('msa','msa_ref') AND table_type='BASE TABLE'
GROUP BY table_schema ORDER BY table_schema;
SELECT count(*) AS core_attributes
FROM information_schema.columns WHERE table_schema IN ('msa','msa_ref');
SELECT obj_description('msa'::regnamespace,'pg_namespace')::jsonb AS migration_ledger;

-- 4. Published build inventory: approved CSV build and separate synthetic fixture build.
SELECT b.key AS dataset_build, b.value->>'published' AS published,
       b.value->>'synthetic' AS synthetic,
       b.value->>'projection_version' AS projection_version
FROM jsonb_each(obj_description('msa_ref'::regnamespace,'pg_namespace')::jsonb->'builds') b
ORDER BY b.key;

-- 5. All six datasets for the exact approved build, excluding synthetic fixtures.
-- Indications and priorities are JSONB arrays, not two extra SQL tables.
WITH approved_build AS (
 SELECT '463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9'::text AS id
), source_rows(dataset,source_id) AS (
 SELECT 'medications',source_medication_id FROM msa_ref.medications
 WHERE dataset_build=(SELECT id FROM approved_build)
 UNION ALL SELECT 'ingredients',source_ingredient_id FROM msa_ref.ingredients
 WHERE dataset_build=(SELECT id FROM approved_build)
 UNION ALL SELECT 'medication_ingredients',source_component_id FROM msa_ref.medication_ingredients
 WHERE dataset_build=(SELECT id FROM approved_build)
 UNION ALL SELECT 'ddinter_mappings',source_mapping_id FROM msa_ref.ddinter_mappings
 WHERE dataset_build=(SELECT id FROM approved_build)
 UNION ALL SELECT 'medication_indications',e->>'id'
 FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.indications) e
 WHERE m.dataset_build=(SELECT id FROM approved_build)
 UNION ALL SELECT 'medication_priorities',e->>'id'
 FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.priorities) e
 WHERE m.dataset_build=(SELECT id FROM approved_build)
), expected(dataset,expected_records) AS (VALUES
 ('medications',10670), ('ingredients',1940), ('medication_ingredients',12899),
 ('ddinter_mappings',5675), ('medication_indications',5614), ('medication_priorities',6105)
), counts AS (
 SELECT e.dataset,e.expected_records,count(r.source_id) AS actual_records,
        count(DISTINCT r.source_id) AS distinct_source_ids
 FROM expected e LEFT JOIN source_rows r USING(dataset)
 GROUP BY e.dataset,e.expected_records
), checked AS (
 SELECT dataset,expected_records::bigint,actual_records,distinct_source_ids,
        CASE WHEN expected_records=actual_records AND actual_records=distinct_source_ids
             THEN 'OK' ELSE 'MISMATCH' END AS status
 FROM counts
)
SELECT * FROM checked
UNION ALL
SELECT 'TOTAL',sum(expected_records)::bigint,sum(actual_records)::bigint,
       sum(distinct_source_ids)::bigint,
       CASE WHEN bool_and(status='OK') THEN 'OK' ELSE 'MISMATCH' END
FROM checked
ORDER BY dataset;

-- 6. PK/FK totals: 20 PKs; 40 validated FKs, all RESTRICT on UPDATE and DELETE.
SELECT count(*) FILTER(WHERE contype='p') AS primary_keys,
       count(*) FILTER(WHERE contype='f') AS foreign_keys,
       count(*) FILTER(WHERE contype='f' AND convalidated) AS validated_foreign_keys,
       count(*) FILTER(WHERE contype='f' AND confupdtype='r' AND confdeltype='r') AS restrictive_foreign_keys
FROM pg_constraint
WHERE connamespace IN ('msa'::regnamespace,'msa_ref'::regnamespace);

-- Exact definitions expose composite owner/build/snapshot/version membership.
SELECT n.nspname AS schema_name, t.relname AS table_name,
       c.conname AS constraint_name,
       CASE c.contype WHEN 'p' THEN 'PRIMARY KEY' ELSE 'FOREIGN KEY' END AS kind,
       pg_get_constraintdef(c.oid,true) AS definition
FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE n.nspname IN ('msa','msa_ref') AND c.contype IN ('p','f')
ORDER BY n.nspname,t.relname,c.contype,c.conname;

-- 7. Existing relationship integrity: every violation count should be zero.
SELECT 'component -> product/build' AS relationship,count(*) AS violations
FROM msa_ref.medication_ingredients c LEFT JOIN msa_ref.medications m
 ON (m.id,m.dataset_build)=(c.medication_id,c.dataset_build) WHERE m.id IS NULL
UNION ALL
SELECT 'component -> ingredient/build',count(*)
FROM msa_ref.medication_ingredients c LEFT JOIN msa_ref.ingredients i
 ON (i.id,i.dataset_build)=(c.ingredient_id,c.dataset_build)
WHERE c.ingredient_id IS NOT NULL AND i.id IS NULL
UNION ALL
SELECT 'mapping -> component/build',count(*)
FROM msa_ref.ddinter_mappings d LEFT JOIN msa_ref.medication_ingredients c
 ON (c.id,c.dataset_build)=(d.component_id,d.dataset_build) WHERE c.id IS NULL
UNION ALL
SELECT 'match -> product/build',count(*)
FROM msa.entry_matches e LEFT JOIN msa_ref.medications m
 ON (m.id,m.dataset_build)=(e.product_id,e.reference_build)
WHERE e.product_id IS NOT NULL AND m.id IS NULL
UNION ALL
SELECT 'snapshot entry -> confirmed version/owner',count(*)
FROM msa.snapshot_entries e LEFT JOIN msa.medication_entry_versions v
 ON (v.id,v.user_id)=(e.entry_version_id,e.user_id)
WHERE v.id IS NULL OR v.confirmed_at IS NULL
UNION ALL
SELECT 'finding -> assessment/snapshot/owner',count(*)
FROM msa.safety_findings f LEFT JOIN msa.safety_assessments a
 ON (a.id,a.snapshot_id,a.user_id)=(f.assessment_id,f.snapshot_id,f.user_id)
WHERE a.id IS NULL
UNION ALL
SELECT 'finding entry -> finding/snapshot/owner',count(*)
FROM msa.finding_entries e LEFT JOIN msa.safety_findings f
 ON (f.id,f.snapshot_id,f.user_id)=(e.finding_id,e.snapshot_id,e.user_id)
WHERE f.id IS NULL
UNION ALL
SELECT 'finding entry -> snapshot entry/owner',count(*)
FROM msa.finding_entries e LEFT JOIN msa.snapshot_entries s
 ON (s.snapshot_id,s.entry_version_id,s.user_id)=(e.snapshot_id,e.entry_version_id,e.user_id)
WHERE s.snapshot_id IS NULL
UNION ALL
SELECT 'summary -> assessment/snapshot/owner',count(*)
FROM msa.patient_health_summaries s LEFT JOIN msa.safety_assessments a
 ON (a.id,a.snapshot_id,a.user_id)=(s.primary_assessment_id,s.medication_snapshot_id,s.user_id)
WHERE s.primary_assessment_id IS NOT NULL AND a.id IS NULL
ORDER BY relationship;

COMMIT;
