# Medication Safety Assistant - Simplified Unified SQL ERD 32 Tables

Phiên bản này rút gọn thiết kế từ 64 còn 32 bảng. Hai hồ sơ `PROFESSIONAL_PROFILES` và `STAFF_PROFILES` được tách khỏi `USERS` vì thông tin chuyên môn y tế và thông tin nhân sự có phạm vi, vòng đời và quy tắc xác minh khác nhau. Audit, evidence, care scope và các entity an toàn quan trọng vẫn được giữ riêng.

```mermaid
erDiagram
    USERS {
        uuid user_id PK
        varchar email UK
        varchar password_hash
        varchar full_name
        varchar phone
        date date_of_birth
        varchar gender
        varchar account_status
        timestamptz last_login_at
        timestamptz created_at
        timestamptz updated_at
    }
    PROFESSIONAL_PROFILES {
        uuid professional_profile_id PK
        uuid user_id FK, UK
        varchar professional_type
        varchar license_number
        varchar license_authority
        varchar specialty
        jsonb qualification_data
        varchar verification_status
        uuid verified_by_user_id FK
        timestamptz verified_at
        timestamptz created_at
        timestamptz updated_at
    }
    STAFF_PROFILES {
        uuid staff_profile_id PK
        uuid user_id FK, UK
        varchar employee_code UK
        varchar department
        varchar job_title
        varchar employment_status
        uuid manager_user_id FK
        timestamptz created_at
        timestamptz updated_at
    }
    ROLES {
        smallint role_id PK
        varchar role_code UK
        varchar role_name
        text description
        jsonb permissions
        boolean is_system_role
        timestamptz created_at
        timestamptz updated_at
    }
    USER_ROLES {
        uuid user_id PK, FK
        smallint role_id PK, FK
        uuid granted_by_user_id FK
        timestamptz granted_at
        timestamptz expires_at
        timestamptz revoked_at
        text revoke_reason
    }
    CARE_RELATIONSHIPS {
        uuid care_relationship_id PK
        uuid patient_user_id FK
        uuid professional_user_id FK
        varchar relationship_type
        varchar status
        timestamptz starts_at
        timestamptz ends_at
        uuid granted_by_user_id FK
        timestamptz created_at
        timestamptz updated_at
    }
    AUDIT_LOGS {
        uuid audit_log_id PK
        uuid actor_user_id FK
        varchar action_code
        varchar target_type
        uuid target_id
        uuid request_id
        varchar ip_address
        text user_agent
        jsonb before_data
        jsonb after_data
        boolean success
        text failure_reason
        timestamptz occurred_at
    }

    MEDICATION_INTAKES {
        uuid intake_id PK
        uuid patient_user_id FK
        uuid submitted_by_user_id FK
        varchar input_method
        text raw_text
        jsonb document_manifest
        varchar source_filename
        text storage_uri
        varchar checksum_sha256
        varchar mime_type
        varchar status
        timestamptz submitted_at
        timestamptz updated_at
    }
    EXTRACTION_RUNS {
        uuid extraction_run_id PK
        uuid intake_id FK
        uuid created_by_user_id FK
        varchar engine_name
        varchar engine_version
        jsonb input_manifest
        varchar status
        jsonb raw_output
        varchar error_code
        text error_message
        timestamptz started_at
        timestamptz completed_at
        timestamptz created_at
    }
    MEDICATION_ENTRIES {
        uuid entry_id PK
        uuid intake_id FK
        uuid patient_user_id FK
        uuid extraction_run_id FK
        uuid prescription_group_id
        integer ordinal
        text raw_text
        varchar extracted_name
        varchar extracted_strength
        varchar extracted_form
        varchar extracted_route
        text dosage_instructions
        varchar prescription_number
        varchar prescriber_name
        date prescription_date
        varchar confirmation_status
        jsonb confirmed_data
        uuid confirmed_by_user_id FK
        timestamptz confirmed_at
        varchar status
        timestamptz created_at
        timestamptz updated_at
    }

    DATASET_VERSIONS {
        uuid version_id PK
        uuid parent_version_id FK
        varchar version_code UK
        varchar name
        text description
        varchar source_package_name
        varchar source_package_hash
        varchar status
        uuid imported_by_user_id FK
        uuid reviewed_by_user_id FK
        uuid released_by_user_id FK
        jsonb import_metadata
        timestamptz created_at
        timestamptz imported_at
        timestamptz approved_at
        timestamptz released_at
        timestamptz retired_at
    }
    SOURCE_RECORDS {
        uuid source_record_id PK
        uuid version_id FK
        varchar source_relation
        varchar source_identifier
        bigint source_row_number
        jsonb source_ref
        jsonb payload
        varchar checksum_sha256
        varchar rule_version
        varchar transformation_status
        varchar validation_status
        jsonb validation_results
        timestamptz created_at
    }
    DATA_REVIEW_ITEMS {
        uuid review_item_id PK
        uuid version_id FK
        uuid source_record_id FK
        varchar entity_type
        uuid entity_id
        varchar field_name
        varchar review_scope
        varchar issue_type
        varchar priority
        varchar status
        uuid assigned_reviewer_user_id FK
        uuid assigned_by_user_id FK
        timestamptz assigned_at
        varchar decision
        text decision_reason
        boolean second_review_required
        uuid second_reviewer_user_id FK
        varchar second_decision
        timestamptz decided_at
        timestamptz created_at
        timestamptz updated_at
    }
    EVIDENCE_SOURCES {
        uuid evidence_source_id PK
        uuid version_id FK
        uuid source_record_id FK
        varchar source_type
        varchar title
        varchar publisher
        text url
        text storage_uri
        text citation
        varchar checksum_sha256
        date published_at
        timestamptz retrieved_at
        jsonb metadata
        timestamptz created_at
    }
    EVIDENCE_LINKS {
        uuid evidence_link_id PK
        uuid evidence_source_id FK
        uuid review_item_id FK
        varchar target_type
        uuid target_id
        varchar relation_type
        text excerpt
        varchar source_locator
        numeric confidence
        uuid created_by_user_id FK
        timestamptz created_at
    }

    MEDICATIONS {
        uuid medication_id PK
        uuid version_id FK
        varchar source_identifier
        varchar brand_name
        varchar generic_name
        varchar registration_number_source
        varchar registration_token
        varchar manufacturer
        varchar dosage_form
        varchar dosage_form_key
        varchar route
        varchar release_characteristic
        text packaging
        varchar identity_state
        varchar composition_state
        boolean complete_composition_verified
        boolean level2_qualified
        varchar collection_priority_tier
        text priority_reason
        boolean active
        jsonb identity_definition
        jsonb issues
        timestamptz created_at
    }
    INGREDIENTS {
        uuid ingredient_id PK
        uuid version_id FK
        varchar source_identifier
        varchar source_name
        varchar normalized_name
        varchar comparison_key
        varchar accepted_name
        varchar accepted_identity_code
        varchar identity_kind
        varchar identity_status
        varchar acceptance_scope
        boolean clinical_identity_verified
        text unresolved_reason
        timestamptz created_at
    }
    MEDICATION_COMPONENTS {
        uuid component_id PK
        uuid version_id FK
        uuid medication_id FK
        uuid ingredient_id FK
        varchar source_identifier
        integer ordinal
        varchar original_name_candidate
        text ingredient_text_raw
        varchar chemical_form_raw
        text equivalence_declaration_raw
        text strength_raw
        numeric amount
        varchar unit
        numeric denominator_amount
        varchar denominator_unit
        varchar strength_basis
        varchar identity_status
        varchar strength_status
        boolean identity_verified
        varchar review_status
        timestamptz created_at
    }
    MEDICATION_INDICATIONS {
        uuid indication_id PK
        uuid version_id FK
        uuid medication_id FK
        uuid review_item_id FK
        uuid evidence_source_id FK
        varchar source_identifier
        text statement
        varchar polarity
        varchar condition_code
        varchar condition_name
        varchar condition_group
        text source_context
        varchar approval_status
        varchar normalization_status
        timestamptz created_at
    }
    SAFETY_DRUG_ENTITIES {
        uuid safety_drug_entity_id PK
        uuid version_id FK
        varchar namespace
        varchar source_code
        varchar preferred_name
        varchar normalized_name
        varchar entity_type
        varchar catalog_hash
        varchar status
        jsonb metadata
        timestamptz created_at
    }
    COMPONENT_SAFETY_MAPPINGS {
        uuid mapping_id PK
        uuid version_id FK
        uuid component_id FK
        uuid safety_drug_entity_id FK
        uuid review_item_id FK
        uuid evidence_source_id FK
        uuid reviewed_by_user_id FK
        varchar mapping_method
        numeric candidate_score
        varchar mapping_status
        boolean accepted
        boolean operative
        text unresolved_reason
        timestamptz reviewed_at
        timestamptz created_at
    }
    DRUG_INTERACTIONS {
        uuid interaction_id PK
        uuid version_id FK
        uuid drug_a_entity_id FK
        uuid drug_b_entity_id FK
        uuid review_item_id FK
        varchar severity_source
        varchar severity_normalized
        text description
        text mechanism
        text clinical_effect
        text management_recommendation
        varchar onset
        varchar evidence_quality
        jsonb evidence_summary
        varchar status
        timestamptz created_at
    }

    ENTRY_IDENTIFICATIONS {
        uuid identification_id PK
        uuid entry_id FK
        uuid version_id FK
        uuid selected_medication_id FK
        varchar method
        varchar status
        numeric confidence
        integer candidate_count
        jsonb candidates
        jsonb matched_fields
        uuid reviewed_by_user_id FK
        timestamptz reviewed_at
        timestamptz created_at
    }
    SAFETY_ASSESSMENTS {
        uuid assessment_id PK
        uuid patient_user_id FK
        uuid version_id FK
        uuid requested_by_user_id FK
        varchar assessment_type
        varchar status
        varchar engine_version
        varchar highest_severity
        text summary
        varchar error_code
        text error_message
        timestamptz requested_at
        timestamptz started_at
        timestamptz completed_at
    }
    ASSESSMENT_ITEMS {
        uuid assessment_item_id PK
        uuid assessment_id FK
        uuid entry_id FK
        uuid identification_id FK
        uuid medication_id FK
        varchar display_name
        jsonb safety_entity_ids
        jsonb source_snapshot
        boolean active
        timestamptz created_at
    }
    SAFETY_FINDINGS {
        uuid finding_id PK
        uuid assessment_id FK
        uuid left_item_id FK
        uuid right_item_id FK
        uuid interaction_id FK
        varchar finding_type
        varchar severity
        varchar title
        text description
        text recommended_action
        jsonb evidence_summary
        varchar status
        timestamptz created_at
    }
    CLINICAL_REVIEWS {
        uuid clinical_review_id PK
        uuid assessment_id FK
        uuid patient_user_id FK
        uuid professional_user_id FK
        uuid care_relationship_id FK
        uuid requested_by_user_id FK
        varchar priority
        varchar status
        text request_reason
        timestamptz assigned_at
        timestamptz started_at
        varchar decision_code
        text clinical_comment
        text recommendation
        timestamptz reviewed_at
        timestamptz closed_at
        timestamptz created_at
    }
    THREADS {
        uuid thread_id PK
        varchar context_type
        uuid context_id
        uuid created_by_user_id FK
        varchar subject
        varchar status
        jsonb participant_scope
        timestamptz created_at
        timestamptz last_message_at
        timestamptz closed_at
    }
    MESSAGES {
        uuid message_id PK
        uuid thread_id FK
        uuid sender_user_id FK
        varchar message_type
        text content
        jsonb attachment_manifest
        jsonb read_receipts
        varchar moderation_status
        timestamptz sent_at
        timestamptz edited_at
        timestamptz deleted_at
    }
    MEDICATION_PLANS {
        uuid plan_id PK
        uuid patient_user_id FK
        uuid entry_id FK
        uuid medication_id FK
        uuid clinical_review_id FK
        uuid created_by_user_id FK
        uuid plan_group_id
        varchar medication_name
        text instructions
        numeric dose_amount
        varchar dose_unit
        varchar route
        varchar frequency_code
        jsonb scheduled_times
        varchar timezone
        date start_date
        date end_date
        varchar eligibility_status
        text eligibility_reason
        varchar status
        timestamptz created_at
        timestamptz updated_at
    }
    REMINDER_EVENTS {
        uuid reminder_event_id PK
        uuid plan_id FK
        uuid recorded_by_user_id FK
        timestamptz scheduled_at
        varchar delivery_channel
        varchar delivery_status
        timestamptz sent_at
        text failure_reason
        varchar response_status
        timestamptz responded_at
        text note
        timestamptz created_at
    }
    SUPPORT_TICKETS {
        uuid ticket_id PK
        uuid created_by_user_id FK
        uuid assigned_to_user_id FK
        uuid thread_id FK
        varchar category
        varchar subject
        text description
        varchar priority
        varchar status
        jsonb diagnostic_context
        jsonb assignment_history
        text resolution_summary
        timestamptz opened_at
        timestamptz assigned_at
        timestamptz resolved_at
        timestamptz closed_at
    }

    USERS ||--o| PROFESSIONAL_PROFILES : "co ho so chuyen mon"
    USERS ||--o| STAFF_PROFILES : "co ho so nhan su"
    USERS o|--o{ PROFESSIONAL_PROFILES : "xac minh chuyen mon"
    USERS o|--o{ STAFF_PROFILES : "quan ly nhan su"
    USERS ||--o{ USER_ROLES : "nhan role"
    ROLES ||--o{ USER_ROLES : "duoc gan"
    USERS o|--o{ USER_ROLES : "cap role"
    USERS ||--o{ CARE_RELATIONSHIPS : "la patient"
    USERS ||--o{ CARE_RELATIONSHIPS : "la professional"
    USERS o|--o{ AUDIT_LOGS : "thuc hien"

    USERS ||--o{ MEDICATION_INTAKES : "so huu"
    USERS ||--o{ MEDICATION_INTAKES : "gui"
    MEDICATION_INTAKES ||--o{ EXTRACTION_RUNS : "duoc trich xuat"
    MEDICATION_INTAKES ||--o{ MEDICATION_ENTRIES : "tao entries"
    EXTRACTION_RUNS o|--o{ MEDICATION_ENTRIES : "sinh ra"
    USERS o|--o{ MEDICATION_ENTRIES : "xac nhan"

    DATASET_VERSIONS o|--o{ DATASET_VERSIONS : "ke thua"
    USERS o|--o{ DATASET_VERSIONS : "import review release"
    DATASET_VERSIONS ||--o{ SOURCE_RECORDS : "chua source"
    DATASET_VERSIONS ||--o{ DATA_REVIEW_ITEMS : "co review"
    SOURCE_RECORDS o|--o{ DATA_REVIEW_ITEMS : "phat sinh"
    USERS o|--o{ DATA_REVIEW_ITEMS : "duoc giao"
    DATASET_VERSIONS ||--o{ EVIDENCE_SOURCES : "quan ly"
    SOURCE_RECORDS o|--o{ EVIDENCE_SOURCES : "tao evidence"
    EVIDENCE_SOURCES ||--o{ EVIDENCE_LINKS : "duoc lien ket"
    DATA_REVIEW_ITEMS o|--o{ EVIDENCE_LINKS : "duoc chung minh"

    DATASET_VERSIONS ||--o{ MEDICATIONS : "chua"
    DATASET_VERSIONS ||--o{ INGREDIENTS : "chua"
    MEDICATIONS ||--|{ MEDICATION_COMPONENTS : "co thanh phan"
    INGREDIENTS o|--o{ MEDICATION_COMPONENTS : "duoc nhan dien"
    MEDICATIONS ||--o{ MEDICATION_INDICATIONS : "co chi dinh"
    EVIDENCE_SOURCES o|--o{ MEDICATION_INDICATIONS : "chung minh"
    DATASET_VERSIONS ||--o{ SAFETY_DRUG_ENTITIES : "chua"
    MEDICATION_COMPONENTS ||--o{ COMPONENT_SAFETY_MAPPINGS : "duoc anh xa"
    SAFETY_DRUG_ENTITIES ||--o{ COMPONENT_SAFETY_MAPPINGS : "la dich"
    DATASET_VERSIONS ||--o{ DRUG_INTERACTIONS : "chua"
    SAFETY_DRUG_ENTITIES ||--o{ DRUG_INTERACTIONS : "dau A"
    SAFETY_DRUG_ENTITIES ||--o{ DRUG_INTERACTIONS : "dau B"

    MEDICATION_ENTRIES ||--o{ ENTRY_IDENTIFICATIONS : "duoc nhan dien"
    DATASET_VERSIONS ||--o{ ENTRY_IDENTIFICATIONS : "cung cap catalog"
    MEDICATIONS o|--o{ ENTRY_IDENTIFICATIONS : "duoc chon"
    USERS o|--o{ ENTRY_IDENTIFICATIONS : "review"
    USERS ||--o{ SAFETY_ASSESSMENTS : "la patient"
    DATASET_VERSIONS ||--o{ SAFETY_ASSESSMENTS : "duoc su dung"
    SAFETY_ASSESSMENTS ||--|{ ASSESSMENT_ITEMS : "dong bang danh sach"
    MEDICATION_ENTRIES ||--o{ ASSESSMENT_ITEMS : "tham gia"
    ENTRY_IDENTIFICATIONS o|--o{ ASSESSMENT_ITEMS : "cung cap identity"
    MEDICATIONS o|--o{ ASSESSMENT_ITEMS : "tham chieu"
    SAFETY_ASSESSMENTS ||--o{ SAFETY_FINDINGS : "tao ket qua"
    ASSESSMENT_ITEMS ||--o{ SAFETY_FINDINGS : "la ben trai"
    ASSESSMENT_ITEMS o|--o{ SAFETY_FINDINGS : "la ben phai"
    DRUG_INTERACTIONS o|--o{ SAFETY_FINDINGS : "khop interaction"

    SAFETY_ASSESSMENTS ||--o{ CLINICAL_REVIEWS : "yeu cau review"
    USERS ||--o{ CLINICAL_REVIEWS : "la patient"
    USERS o|--o{ CLINICAL_REVIEWS : "la professional"
    CARE_RELATIONSHIPS o|--o{ CLINICAL_REVIEWS : "cap pham vi"
    USERS ||--o{ THREADS : "tao thread"
    THREADS ||--o{ MESSAGES : "chua"
    USERS ||--o{ MESSAGES : "gui"

    USERS ||--o{ MEDICATION_PLANS : "co ke hoach"
    MEDICATION_ENTRIES o|--o{ MEDICATION_PLANS : "lam nguon"
    MEDICATIONS o|--o{ MEDICATION_PLANS : "tham chieu"
    CLINICAL_REVIEWS o|--o{ MEDICATION_PLANS : "lam can cu"
    MEDICATION_PLANS ||--o{ REMINDER_EVENTS : "tao reminder"
    USERS o|--o{ REMINDER_EVENTS : "ghi nhan"

    USERS ||--o{ SUPPORT_TICKETS : "tao ticket"
    USERS o|--o{ SUPPORT_TICKETS : "duoc giao"
    THREADS o|--o| SUPPORT_TICKETS : "trao doi"
```

## Các ràng buộc cần triển khai khi chuyển thành SQL

- `USER_ROLES`: unique `(user_id, role_id)` đối với role chưa bị thu hồi.
- `PROFESSIONAL_PROFILES`: mỗi user có tối đa một hồ sơ chuyên môn; `verification_status=VERIFIED` phải có người và thời điểm xác minh.
- `STAFF_PROFILES`: mỗi user có tối đa một hồ sơ nhân sự; `employee_code` là duy nhất khi được cấp.
- `CARE_RELATIONSHIPS`: patient và professional phải khác nhau; khoảng hiệu lực không được đảo ngược.
- `SOURCE_RECORDS`: unique `(version_id, source_relation, source_identifier)`.
- `MEDICATION_COMPONENTS`: unique `(medication_id, ordinal)` trong cùng version.
- `COMPONENT_SAFETY_MAPPINGS`: chỉ mapping đã review mới được `operative=true`.
- `DRUG_INTERACTIONS`: `drug_a_entity_id <> drug_b_entity_id`; chuẩn hóa thứ tự A/B và unique theo version.
- `ASSESSMENT_ITEMS`: immutable sau khi assessment bắt đầu chạy.
- `SAFETY_FINDINGS`: `right_item_id` có thể null cho cảnh báo một thuốc; interaction pair phải có đủ hai item.
- `REMINDER_EVENTS`: unique `(plan_id, scheduled_at)` để tránh gửi trùng.
- `AUDIT_LOGS`, `DATA_REVIEW_ITEMS` đã quyết định và evidence đã phát hành phải được coi là append-only.

