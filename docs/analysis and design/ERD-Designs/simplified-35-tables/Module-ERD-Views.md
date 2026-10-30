# Medication Safety Assistant - Simplified Module ERD Views 35 Tables

Mỗi sơ đồ dưới đây chỉ hiển thị các bảng mà module trực tiếp đọc hoặc ghi. Thuộc tính được giữ nhất quán với `Unified-SQL-ERD.md`.

## Module 1 - Medication Intake

```mermaid
erDiagram
    USERS {
        uuid user_id PK
        varchar email UK
        varchar password_hash
        varchar full_name
        varchar phone
        date date_of_birth
        varchar account_status
        timestamptz created_at
        timestamptz updated_at
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

    USERS ||--o{ MEDICATION_INTAKES : "so huu"
    USERS ||--o{ MEDICATION_INTAKES : "gui"
    MEDICATION_INTAKES ||--o{ EXTRACTION_RUNS : "duoc trich xuat"
    USERS o|--o{ EXTRACTION_RUNS : "kich hoat"
    MEDICATION_INTAKES ||--o{ MEDICATION_ENTRIES : "tao entries"
    EXTRACTION_RUNS o|--o{ MEDICATION_ENTRIES : "sinh ra"
    USERS ||--o{ MEDICATION_ENTRIES : "la patient"
    USERS o|--o{ MEDICATION_ENTRIES : "xac nhan"
```

## Module 2 - Medication Identification and Reference

```mermaid
erDiagram
    MEDICATION_ENTRIES {
        uuid entry_id PK
        uuid patient_user_id FK
        text raw_text
        varchar extracted_name
        varchar extracted_strength
        varchar extracted_form
        varchar extracted_route
        varchar confirmation_status
        jsonb confirmed_data
        varchar status
        timestamptz updated_at
    }
    DATASET_VERSIONS {
        uuid version_id PK
        varchar version_code UK
        varchar name
        varchar source_package_hash
        varchar status
        timestamptz approved_at
        timestamptz released_at
        timestamptz retired_at
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

    MEDICATION_ENTRIES ||--o{ ENTRY_IDENTIFICATIONS : "duoc nhan dien"
    DATASET_VERSIONS ||--o{ ENTRY_IDENTIFICATIONS : "cung cap catalog"
    MEDICATIONS o|--o{ ENTRY_IDENTIFICATIONS : "duoc chon"
    DATASET_VERSIONS ||--o{ MEDICATIONS : "chua"
    DATASET_VERSIONS ||--o{ INGREDIENTS : "chua"
    MEDICATIONS ||--|{ MEDICATION_COMPONENTS : "co thanh phan"
    INGREDIENTS o|--o{ MEDICATION_COMPONENTS : "duoc nhan dien"
    MEDICATIONS ||--o{ MEDICATION_INDICATIONS : "co chi dinh"
    EVIDENCE_SOURCES o|--o{ MEDICATION_INDICATIONS : "chung minh"
```

## Module 3 - Medication Safety Assessment

```mermaid
erDiagram
    DATASET_VERSIONS {
        uuid version_id PK
        varchar version_code UK
        varchar status
        varchar source_package_hash
        timestamptz released_at
        timestamptz retired_at
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
    MEDICATION_COMPONENTS {
        uuid component_id PK
        uuid medication_id FK
        uuid ingredient_id FK
        text ingredient_text_raw
        text strength_raw
        varchar identity_status
        varchar strength_status
        boolean identity_verified
        varchar review_status
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

    DATASET_VERSIONS ||--o{ SAFETY_ASSESSMENTS : "duoc su dung"
    SAFETY_ASSESSMENTS ||--|{ ASSESSMENT_ITEMS : "dong bang danh sach"
    SAFETY_ASSESSMENTS ||--o{ SAFETY_FINDINGS : "tao finding"
    ASSESSMENT_ITEMS ||--o{ SAFETY_FINDINGS : "la ben trai"
    ASSESSMENT_ITEMS o|--o{ SAFETY_FINDINGS : "la ben phai"
    MEDICATION_COMPONENTS ||--o{ COMPONENT_SAFETY_MAPPINGS : "duoc anh xa"
    SAFETY_DRUG_ENTITIES ||--o{ COMPONENT_SAFETY_MAPPINGS : "la dich"
    SAFETY_DRUG_ENTITIES ||--o{ DRUG_INTERACTIONS : "dau A"
    SAFETY_DRUG_ENTITIES ||--o{ DRUG_INTERACTIONS : "dau B"
    DRUG_INTERACTIONS o|--o{ SAFETY_FINDINGS : "khop"
    EVIDENCE_SOURCES ||--o{ EVIDENCE_LINKS : "duoc lien ket"
```

## Module 4 - HCP Review

```mermaid
erDiagram
    USERS {
        uuid user_id PK
        varchar email UK
        varchar full_name
        varchar phone
        varchar account_status
        timestamptz created_at
    }
    ROLES {
        smallint role_id PK
        varchar role_code UK "hcp"
        varchar role_name
        jsonb permissions
        boolean is_system_role
    }
    USER_ROLES {
        uuid user_id PK, FK
        smallint role_id PK, FK
        uuid granted_by_user_id FK
        timestamptz granted_at
        timestamptz expires_at
        timestamptz revoked_at
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
    SAFETY_ASSESSMENTS {
        uuid assessment_id PK
        uuid patient_user_id FK
        uuid version_id FK
        uuid requested_by_user_id FK
        varchar assessment_type
        varchar status
        varchar highest_severity
        text summary
        timestamptz requested_at
        timestamptz completed_at
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
        varchar sender_type
        varchar message_type
        text content
        jsonb attachment_manifest
        jsonb read_receipts
        varchar moderation_status
        varchar model_name
        varchar model_version
        varchar prompt_version
        timestamptz generated_at
        timestamptz sent_at
        timestamptz edited_at
        timestamptz deleted_at
    }

    USERS ||--o| PROFESSIONAL_PROFILES : "co ho so chuyen mon"
    USERS o|--o{ PROFESSIONAL_PROFILES : "xac minh"
    USERS ||--o{ USER_ROLES : "nhan role HCP"
    ROLES ||--o{ USER_ROLES : "hcp"
    USERS ||--o{ CARE_RELATIONSHIPS : "la patient"
    USERS ||--o{ CARE_RELATIONSHIPS : "la professional"
    SAFETY_ASSESSMENTS ||--o{ SAFETY_FINDINGS : "co ket qua"
    SAFETY_ASSESSMENTS ||--o{ CLINICAL_REVIEWS : "yeu cau review"
    USERS ||--o{ CLINICAL_REVIEWS : "la patient"
    USERS o|--o{ CLINICAL_REVIEWS : "HCP duoc phan cong"
    CARE_RELATIONSHIPS o|--o{ CLINICAL_REVIEWS : "cap pham vi"
    USERS ||--o{ THREADS : "tao"
    THREADS ||--o{ MESSAGES : "chua"
    USERS ||--o{ MESSAGES : "gui"
```

Module này là review lâm sàng theo từng bệnh nhân và yêu cầu role `hcp`. Review dữ liệu danh mục thuốc của `medical_reviewer` được thể hiện riêng trong Shared Domain - Data Import Review and Release.

## Module 5 - Medication Plans and Reminders

```mermaid
erDiagram
    USERS {
        uuid user_id PK
        varchar email UK
        varchar full_name
        varchar phone
        varchar account_status
        timestamptz created_at
        timestamptz updated_at
    }
    MEDICATION_ENTRIES {
        uuid entry_id PK
        uuid patient_user_id FK
        varchar extracted_name
        varchar extracted_strength
        text dosage_instructions
        varchar confirmation_status
        jsonb confirmed_data
        varchar status
        timestamptz updated_at
    }
    MEDICATIONS {
        uuid medication_id PK
        uuid version_id FK
        varchar brand_name
        varchar generic_name
        varchar registration_token
        varchar dosage_form
        varchar route
        boolean active
    }
    CLINICAL_REVIEWS {
        uuid clinical_review_id PK
        uuid assessment_id FK
        uuid patient_user_id FK
        uuid professional_user_id FK
        varchar status
        varchar decision_code
        text recommendation
        timestamptz reviewed_at
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
    MEDICATION_USAGE_EVENTS {
        uuid usage_event_id PK
        uuid plan_id FK
        uuid patient_user_id FK
        uuid reminder_event_id FK
        timestamptz scheduled_at
        timestamptz actual_taken_at
        numeric dose_amount
        varchar dose_unit
        varchar usage_status
        varchar source_type
        uuid recorded_by_user_id FK
        text skip_reason
        text notes
        timestamptz created_at
    }

    USERS ||--o{ MEDICATION_ENTRIES : "la patient"
    USERS ||--o{ MEDICATION_PLANS : "co ke hoach"
    MEDICATION_ENTRIES o|--o{ MEDICATION_PLANS : "lam nguon"
    MEDICATIONS o|--o{ MEDICATION_PLANS : "tham chieu"
    CLINICAL_REVIEWS o|--o{ MEDICATION_PLANS : "lam can cu"
    MEDICATION_PLANS ||--o{ REMINDER_EVENTS : "tao event"
    USERS o|--o{ REMINDER_EVENTS : "ghi nhan phan hoi"
    MEDICATION_PLANS ||--o{ MEDICATION_USAGE_EVENTS : "co lich su su dung"
    REMINDER_EVENTS o|--o| MEDICATION_USAGE_EVENTS : "co the ghi nhan"
    USERS ||--o{ MEDICATION_USAGE_EVENTS : "la patient"
    USERS o|--o{ MEDICATION_USAGE_EVENTS : "ghi nhan"
```

## Module 6 - Patient Health Chatbot

```mermaid
erDiagram
    USERS {
        uuid user_id PK
        varchar email UK
        varchar full_name
        date date_of_birth
        varchar gender
        varchar account_status
        timestamptz created_at
        timestamptz updated_at
    }
    ROLES {
        smallint role_id PK
        varchar role_code UK "technical_support"
        varchar role_name
        jsonb permissions
        boolean is_system_role
    }
    USER_ROLES {
        uuid user_id PK, FK
        smallint role_id PK, FK
        uuid granted_by_user_id FK
        timestamptz granted_at
        timestamptz expires_at
        timestamptz revoked_at
    }
    STAFF_PROFILES {
        uuid staff_profile_id PK
        uuid user_id FK, UK
        varchar employee_code UK
        varchar department
        varchar job_title
        varchar employment_status
        uuid manager_user_id FK
    }
    PATIENT_PROFILES {
        uuid patient_profile_id PK
        uuid user_id FK, UK
        varchar blood_type
        numeric height_cm
        numeric weight_kg
        varchar pregnancy_status
        varchar renal_status
        varchar hepatic_status
        text health_summary
        jsonb emergency_contact
        timestamptz created_at
        timestamptz updated_at
    }
    PATIENT_CLINICAL_FACTS {
        uuid clinical_fact_id PK
        uuid patient_profile_id FK
        varchar fact_type
        varchar code_system
        varchar fact_code
        varchar fact_name
        uuid ingredient_id FK
        uuid medication_id FK
        varchar clinical_status
        varchar severity
        text reaction
        varchar verification_status
        uuid recorded_by_user_id FK
        uuid verified_by_user_id FK
        date onset_date
        date resolved_date
        text notes
        timestamptz created_at
        timestamptz updated_at
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
        varchar sender_type
        varchar message_type
        text content
        jsonb attachment_manifest
        jsonb read_receipts
        varchar moderation_status
        varchar model_name
        varchar model_version
        varchar prompt_version
        timestamptz generated_at
        timestamptz sent_at
        timestamptz edited_at
        timestamptz deleted_at
    }
    MEDICATION_PLANS {
        uuid plan_id PK
        uuid patient_user_id FK
        uuid medication_id FK
        varchar medication_name
        text instructions
        numeric dose_amount
        varchar dose_unit
        varchar frequency_code
        jsonb scheduled_times
        varchar timezone
        date start_date
        date end_date
        varchar status
    }
    MEDICATION_USAGE_EVENTS {
        uuid usage_event_id PK
        uuid plan_id FK
        uuid patient_user_id FK
        uuid reminder_event_id FK
        timestamptz scheduled_at
        timestamptz actual_taken_at
        numeric dose_amount
        varchar dose_unit
        varchar usage_status
        varchar source_type
        uuid recorded_by_user_id FK
        text skip_reason
        text notes
        timestamptz created_at
    }
    SAFETY_ASSESSMENTS {
        uuid assessment_id PK
        uuid patient_user_id FK
        uuid version_id FK
        uuid requested_by_user_id FK
        varchar status
        varchar highest_severity
        text summary
        timestamptz requested_at
        timestamptz completed_at
    }
    SAFETY_FINDINGS {
        uuid finding_id PK
        uuid assessment_id FK
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
        varchar priority
        varchar status
        text request_reason
        text recommendation
        timestamptz reviewed_at
    }
    SUPPORT_TICKETS {
        uuid ticket_id PK
        uuid created_by_user_id FK
        uuid assigned_to_user_id FK
        uuid thread_id FK
        varchar category
        varchar subject
        varchar priority
        varchar status
        jsonb diagnostic_context
        text resolution_summary
        timestamptz opened_at
        timestamptz closed_at
    }

    USERS ||--o| PATIENT_PROFILES : "co ho so suc khoe"
    USERS ||--o{ USER_ROLES : "nhan role support"
    ROLES ||--o{ USER_ROLES : "technical_support"
    USERS ||--o| STAFF_PROFILES : "co ho so nhan su"
    PATIENT_PROFILES ||--o{ PATIENT_CLINICAL_FACTS : "co clinical facts"
    USERS o|--o{ PATIENT_CLINICAL_FACTS : "ghi nhan xac minh"
    USERS ||--o{ THREADS : "tao hoi thoai"
    THREADS ||--o{ MESSAGES : "chua"
    USERS o|--o{ MESSAGES : "gui neu la user"
    USERS ||--o{ MEDICATION_PLANS : "co ke hoach"
    MEDICATION_PLANS ||--o{ MEDICATION_USAGE_EVENTS : "co lich su su dung"
    USERS ||--o{ MEDICATION_USAGE_EVENTS : "la patient"
    USERS o|--o{ MEDICATION_USAGE_EVENTS : "ghi nhan"
    USERS ||--o{ SAFETY_ASSESSMENTS : "duoc danh gia"
    SAFETY_ASSESSMENTS ||--o{ SAFETY_FINDINGS : "tao finding"
    SAFETY_ASSESSMENTS ||--o{ CLINICAL_REVIEWS : "chuyen HCP"
    USERS ||--o{ SUPPORT_TICKETS : "tao ticket"
    USERS o|--o{ SUPPORT_TICKETS : "technical support duoc giao"
    THREADS o|--o| SUPPORT_TICKETS : "trao doi support"
```

Chatbot tái sử dụng `THREADS` và `MESSAGES`; không tạo bảng hội thoại riêng. Khi cần hỗ trợ kỹ thuật, ticket chỉ được giao cho user có role `technical_support`; hồ sơ nhân sự của người xử lý nằm trong `STAFF_PROFILES`. Nội dung bệnh nhân cung cấp chỉ tạo `PATIENT_CLINICAL_FACTS` ở trạng thái chưa xác minh. Chatbot đọc kết luận an toàn từ `SAFETY_FINDINGS`, không tự suy luận tương tác từ mapping ứng viên.

