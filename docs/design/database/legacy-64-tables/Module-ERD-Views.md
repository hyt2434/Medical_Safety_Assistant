# Medication Safety Assistant - Module ERD Views

File này gom năm ERD view theo module vào một nơi để đọc và kiểm tra luồng liên module. Mỗi phần là một `erDiagram` độc lập; các bảng lặp lại giữa các phần vẫn là cùng một bảng trong database.

Nguồn chuẩn: [Unified SQL ERD](Medication-Safety-Assistant-Unified-SQL-ERD.md).

## Mục lục

1. [Module 1 - Medication Intake](#module-1---medication-intake)
2. [Module 2 - Medication Identification and Reference](#module-2---medication-identification-and-reference)
3. [Module 3 - Medication Safety Assessment](#module-3---medication-safety-assessment)
4. [Module 4 - HCP Review](#module-4---hcp-review)
5. [Module 5 - Medication Reminders](#module-5---medication-reminders)

## Module 1 - Medication Intake

Thu nhận ảnh, PDF, text, voice hoặc dữ liệu nhập tay; lưu từng lần trích xuất và xác nhận dòng thuốc.

```mermaid
---
id: 89da2f5e-84f4-41b4-8c81-e2045e78be6c
---
erDiagram
    USERS {
        uuid user_id PK
    }
    PATIENT_PROFILES {
        uuid patient_id PK
        uuid user_id FK
    }
    MEDICATION_INTAKES {
        uuid intake_id PK
        uuid submitted_by_user_id FK
        uuid patient_id FK
    }
    INTAKE_DOCUMENTS {
        uuid document_id PK
        uuid intake_id FK
    }
    EXTRACTION_RUNS {
        uuid extraction_run_id PK
        uuid intake_id FK
    }
    EXTRACTION_RUN_INPUTS {
        uuid extraction_run_id PK, FK
        uuid document_id PK, FK
    }
    PRESCRIPTIONS {
        uuid prescription_id PK
        uuid patient_id FK
    }
    MEDICATION_ENTRIES {
        uuid entry_id PK
        uuid intake_id FK
        uuid extraction_run_id FK
        uuid prescription_id FK
    }
    ENTRY_CONFIRMATIONS {
        uuid confirmation_id PK
        uuid entry_id FK
        uuid confirmed_by_user_id FK
    }

    USERS ||--o| PATIENT_PROFILES : "có hồ sơ patient"
    USERS ||--o{ MEDICATION_INTAKES : "gửi"
    PATIENT_PROFILES ||--o{ MEDICATION_INTAKES : "là chủ hồ sơ"
    MEDICATION_INTAKES ||--o{ INTAKE_DOCUMENTS : "có tài liệu"
    MEDICATION_INTAKES ||--o{ EXTRACTION_RUNS : "được xử lý"
    EXTRACTION_RUNS ||--o{ EXTRACTION_RUN_INPUTS : "dùng tài liệu"
    INTAKE_DOCUMENTS ||--o{ EXTRACTION_RUN_INPUTS : "là đầu vào"
    PATIENT_PROFILES ||--o{ PRESCRIPTIONS : "sở hữu"
    MEDICATION_INTAKES ||--o{ MEDICATION_ENTRIES : "tạo dòng thuốc"
    EXTRACTION_RUNS o|--o{ MEDICATION_ENTRIES : "trích xuất"
    PRESCRIPTIONS o|--o{ MEDICATION_ENTRIES : "gồm"
    MEDICATION_ENTRIES ||--o{ ENTRY_CONFIRMATIONS : "được xác nhận"
    USERS ||--o{ ENTRY_CONFIRMATIONS : "xác nhận"
```

Một intake có thể chưa tạo được dòng thuốc nếu quá trình trích xuất thất bại. Dòng nhập tay có thể không có `EXTRACTION_RUNS`; thuốc không xuất phát từ đơn có thể không có `PRESCRIPTIONS`.

---

## Module 2 - Medication Identification and Reference

Nhận diện dòng thuốc dựa trên một dataset release, giữ các ứng viên và lấy đầy đủ thành phần của sản phẩm.

```mermaid
erDiagram
    MEDICATION_ENTRIES {
        uuid entry_id PK
    }
    DATASET_VERSIONS {
        uuid version_id PK
    }
    DATASET_RELEASES {
        uuid release_id PK
        uuid version_id FK
    }
    ENTRY_IDENTIFICATIONS {
        uuid identification_id PK
        uuid entry_id FK
        uuid release_id FK
    }
    IDENTIFICATION_CANDIDATES {
        uuid candidate_id PK
        uuid identification_id FK
        uuid medication_id FK
    }
    MEDICATIONS {
        uuid medication_id PK
        uuid version_id FK
    }
    INGREDIENTS {
        uuid ingredient_id PK
        uuid version_id FK
    }
    MEDICATION_COMPONENTS {
        uuid component_id PK
        uuid medication_id FK
        uuid ingredient_id FK
    }
    STRENGTH_ASSERTIONS {
        uuid strength_assertion_id PK
        uuid component_id FK
    }
    MEDICATION_INDICATIONS {
        uuid indication_id PK
        uuid medication_id FK
    }
    CONDITIONS {
        uuid condition_id PK
        uuid version_id FK
    }
    INDICATION_CONDITIONS {
        uuid indication_id PK, FK
        uuid condition_id PK, FK
    }
    MEDICATION_PRIORITIES {
        uuid priority_id PK
        uuid medication_id FK
    }

    DATASET_VERSIONS ||--o{ DATASET_RELEASES : "được phát hành"
    DATASET_VERSIONS ||--o{ MEDICATIONS : "chứa"
    DATASET_VERSIONS ||--o{ INGREDIENTS : "chứa"
    DATASET_VERSIONS ||--o{ CONDITIONS : "chứa"
    MEDICATION_ENTRIES ||--o{ ENTRY_IDENTIFICATIONS : "được nhận diện"
    DATASET_RELEASES ||--o{ ENTRY_IDENTIFICATIONS : "cung cấp dữ liệu"
    ENTRY_IDENTIFICATIONS ||--o{ IDENTIFICATION_CANDIDATES : "có ứng viên"
    MEDICATIONS ||--o{ IDENTIFICATION_CANDIDATES : "được đề xuất"
    MEDICATIONS ||--o{ MEDICATION_COMPONENTS : "có thành phần"
    INGREDIENTS o|--o{ MEDICATION_COMPONENTS : "nhận diện là"
    MEDICATION_COMPONENTS ||--o{ STRENGTH_ASSERTIONS : "có hàm lượng"
    MEDICATIONS ||--o{ MEDICATION_INDICATIONS : "có chỉ định"
    MEDICATION_INDICATIONS ||--o{ INDICATION_CONDITIONS : "dùng điều kiện"
    CONDITIONS ||--o{ INDICATION_CONDITIONS : "được áp dụng"
    MEDICATIONS ||--o{ MEDICATION_PRIORITIES : "có ưu tiên"
```

Một sản phẩm có thể chưa có thành phần đã giải quyết hoàn chỉnh. `IDENTIFICATION_CANDIDATES` chỉ là ứng viên; trạng thái được chọn hoặc xác minh thuộc lần `ENTRY_IDENTIFICATIONS`.

---

## Module 3 - Medication Safety Assessment

Đóng băng danh sách thuốc, ánh xạ thành phần sang ID của nguồn an toàn, tra từng cặp và lưu mọi kết quả đánh giá.

```mermaid
erDiagram
    PATIENT_PROFILES {
        uuid patient_id PK
    }
    MEDICATION_ENTRIES {
        uuid entry_id PK
    }
    ENTRY_IDENTIFICATIONS {
        uuid identification_id PK
    }
    DATASET_VERSIONS {
        uuid version_id PK
    }
    DATASET_RELEASES {
        uuid release_id PK
        uuid version_id FK
    }
    MEDICATION_COMPONENTS {
        uuid component_id PK
    }
    SAFETY_DRUG_ENTITIES {
        uuid safety_drug_entity_id PK
        uuid version_id FK
    }
    COMPONENT_SAFETY_MAPPINGS {
        uuid mapping_id PK
        uuid component_id FK
        uuid safety_drug_entity_id FK
    }
    DRUG_INTERACTIONS {
        uuid interaction_id PK
        uuid version_id FK
    }
    DRUG_INTERACTION_PARTICIPANTS {
        uuid interaction_id PK, FK
        uuid safety_drug_entity_id PK, FK
    }
    EVIDENCE_SOURCES {
        uuid evidence_source_id PK
    }
    INTERACTION_EVIDENCE {
        uuid interaction_evidence_id PK
        uuid interaction_id FK
        uuid evidence_source_id FK
    }
    MEDICATION_LIST_SNAPSHOTS {
        uuid snapshot_id PK
        uuid patient_id FK
    }
    SNAPSHOT_ITEMS {
        uuid snapshot_item_id PK
        uuid snapshot_id FK
        uuid entry_id FK
        uuid identification_id FK
    }
    SAFETY_ASSESSMENTS {
        uuid assessment_id PK
        uuid snapshot_id FK
        uuid release_id FK
    }
    ASSESSMENT_PAIR_RESULTS {
        uuid pair_result_id PK
        uuid assessment_id FK
        uuid left_snapshot_item_id FK
        uuid right_snapshot_item_id FK
        uuid interaction_id FK
    }
    SAFETY_FINDINGS {
        uuid finding_id PK
        uuid assessment_id FK
        uuid interaction_id FK
    }
    FINDING_ITEMS {
        uuid finding_id PK, FK
        uuid snapshot_item_id PK, FK
    }

    DATASET_VERSIONS ||--o{ DATASET_RELEASES : "được phát hành"
    DATASET_VERSIONS ||--o{ SAFETY_DRUG_ENTITIES : "chứa"
    DATASET_VERSIONS ||--o{ DRUG_INTERACTIONS : "chứa"
    MEDICATION_COMPONENTS ||--o{ COMPONENT_SAFETY_MAPPINGS : "được ánh xạ"
    SAFETY_DRUG_ENTITIES o|--o{ COMPONENT_SAFETY_MAPPINGS : "là đích"
    DRUG_INTERACTIONS ||--|{ DRUG_INTERACTION_PARTICIPANTS : "có đầu cặp"
    SAFETY_DRUG_ENTITIES ||--o{ DRUG_INTERACTION_PARTICIPANTS : "tham gia"
    DRUG_INTERACTIONS ||--|{ INTERACTION_EVIDENCE : "có bằng chứng"
    EVIDENCE_SOURCES ||--o{ INTERACTION_EVIDENCE : "chứng minh"
    PATIENT_PROFILES ||--o{ MEDICATION_LIST_SNAPSHOTS : "có danh sách"
    MEDICATION_LIST_SNAPSHOTS ||--|{ SNAPSHOT_ITEMS : "gồm"
    MEDICATION_ENTRIES ||--o{ SNAPSHOT_ITEMS : "được đưa vào"
    ENTRY_IDENTIFICATIONS o|--o{ SNAPSHOT_ITEMS : "dùng nhận diện"
    MEDICATION_LIST_SNAPSHOTS ||--o{ SAFETY_ASSESSMENTS : "được đánh giá"
    DATASET_RELEASES ||--o{ SAFETY_ASSESSMENTS : "cung cấp dữ liệu"
    SAFETY_ASSESSMENTS ||--o{ ASSESSMENT_PAIR_RESULTS : "có kết quả cặp"
    SNAPSHOT_ITEMS ||--o{ ASSESSMENT_PAIR_RESULTS : "là phía trái"
    SNAPSHOT_ITEMS ||--o{ ASSESSMENT_PAIR_RESULTS : "là phía phải"
    DRUG_INTERACTIONS o|--o{ ASSESSMENT_PAIR_RESULTS : "khớp tương tác"
    SAFETY_ASSESSMENTS ||--o{ SAFETY_FINDINGS : "tạo phát hiện"
    DRUG_INTERACTIONS o|--o{ SAFETY_FINDINGS : "được tham chiếu"
    SAFETY_FINDINGS ||--o{ FINDING_ITEMS : "liên quan"
    SNAPSHOT_ITEMS ||--o{ FINDING_ITEMS : "tham gia"
```

Mỗi `DRUG_INTERACTIONS` phải có đúng hai participant khác nhau; SQL/logic giao dịch cần thực thi giới hạn này. “Không có bản ghi” phải được lưu trong `ASSESSMENT_PAIR_RESULTS`, không được chuyển thành kết luận an toàn.

---

## Module 4 - HCP Review

Tạo yêu cầu đánh giá từ một safety assessment, kiểm soát phạm vi truy cập, trao đổi với patient và lưu quyết định chuyên môn.

```mermaid
erDiagram
    USERS {
        uuid user_id PK
    }
    PATIENT_PROFILES {
        uuid patient_id PK
        uuid user_id FK
    }
    PROFESSIONAL_PROFILES {
        uuid professional_id PK
        uuid user_id FK
    }
    CARE_RELATIONSHIPS {
        uuid care_relationship_id PK
        uuid patient_id FK
        uuid professional_id FK
    }
    SAFETY_ASSESSMENTS {
        uuid assessment_id PK
    }
    HCP_REVIEW_REQUESTS {
        uuid hcp_review_request_id PK
        uuid assessment_id FK
        uuid patient_id FK
        uuid care_relationship_id FK
        uuid assigned_professional_id FK
    }
    HCP_REVIEWS {
        uuid hcp_review_id PK
        uuid hcp_review_request_id FK
        uuid professional_id FK
    }
    CONVERSATIONS {
        uuid conversation_id PK
        uuid hcp_review_request_id FK
    }
    CONVERSATION_PARTICIPANTS {
        uuid conversation_id PK, FK
        uuid user_id PK, FK
    }
    MESSAGES {
        uuid message_id PK
        uuid conversation_id FK
        uuid sender_user_id FK
    }
    MEDICATION_REGIMENS {
        uuid regimen_id PK
    }
    REGIMEN_REVIEW_LINKS {
        uuid hcp_review_id PK, FK
        uuid regimen_id PK, FK
    }

    USERS ||--o| PATIENT_PROFILES : "có hồ sơ patient"
    USERS ||--o| PROFESSIONAL_PROFILES : "có hồ sơ chuyên môn"
    PATIENT_PROFILES ||--o{ CARE_RELATIONSHIPS : "được chăm sóc"
    PROFESSIONAL_PROFILES ||--o{ CARE_RELATIONSHIPS : "phụ trách"
    SAFETY_ASSESSMENTS ||--o{ HCP_REVIEW_REQUESTS : "được yêu cầu review"
    PATIENT_PROFILES ||--o{ HCP_REVIEW_REQUESTS : "là patient"
    CARE_RELATIONSHIPS o|--o{ HCP_REVIEW_REQUESTS : "cấp phạm vi"
    PROFESSIONAL_PROFILES o|--o{ HCP_REVIEW_REQUESTS : "được phân công"
    HCP_REVIEW_REQUESTS ||--o{ HCP_REVIEWS : "có quyết định"
    PROFESSIONAL_PROFILES ||--o{ HCP_REVIEWS : "thực hiện"
    HCP_REVIEW_REQUESTS o|--o{ CONVERSATIONS : "có hội thoại"
    CONVERSATIONS ||--|{ CONVERSATION_PARTICIPANTS : "có thành viên"
    USERS ||--o{ CONVERSATION_PARTICIPANTS : "tham gia"
    CONVERSATIONS ||--o{ MESSAGES : "chứa"
    USERS ||--o{ MESSAGES : "gửi"
    HCP_REVIEWS ||--o{ REGIMEN_REVIEW_LINKS : "làm căn cứ"
    MEDICATION_REGIMENS ||--o{ REGIMEN_REVIEW_LINKS : "được review"
```

`HCP_REVIEWS` là quyết định cho trường hợp patient. Nó không thay thế `DATA_REVIEW_DECISIONS`, vốn dùng để duyệt dữ liệu tham chiếu chung.

---

## Module 5 - Medication Reminders

Quản lý phác đồ/lịch dùng thuốc, kiểm tra điều kiện kích hoạt, tạo từng lần nhắc và ghi nhận tuân thủ.

```mermaid
erDiagram
    USERS {
        uuid user_id PK
    }
    PATIENT_PROFILES {
        uuid patient_id PK
    }
    MEDICATION_ENTRIES {
        uuid entry_id PK
    }
    MEDICATION_REGIMENS {
        uuid regimen_id PK
        uuid patient_id FK
    }
    REGIMEN_ITEMS {
        uuid regimen_item_id PK
        uuid regimen_id FK
        uuid entry_id FK
    }
    HCP_REVIEWS {
        uuid hcp_review_id PK
    }
    REGIMEN_REVIEW_LINKS {
        uuid hcp_review_id PK, FK
        uuid regimen_id PK, FK
    }
    REMINDER_SCHEDULES {
        uuid schedule_id PK
        uuid regimen_item_id FK
    }
    SAFETY_ASSESSMENTS {
        uuid assessment_id PK
    }
    SCHEDULE_ELIGIBILITY_CHECKS {
        uuid eligibility_check_id PK
        uuid schedule_id FK
        uuid assessment_id FK
        uuid hcp_review_id FK
    }
    REMINDER_EVENTS {
        uuid reminder_event_id PK
        uuid schedule_id FK
    }
    ADHERENCE_RECORDS {
        uuid adherence_record_id PK
        uuid regimen_item_id FK
        uuid reminder_event_id FK
        uuid recorded_by_user_id FK
    }

    PATIENT_PROFILES ||--o{ MEDICATION_REGIMENS : "có phác đồ"
    MEDICATION_REGIMENS ||--|{ REGIMEN_ITEMS : "gồm"
    MEDICATION_ENTRIES ||--o{ REGIMEN_ITEMS : "được lên lịch"
    HCP_REVIEWS ||--o{ REGIMEN_REVIEW_LINKS : "làm căn cứ"
    MEDICATION_REGIMENS ||--o{ REGIMEN_REVIEW_LINKS : "được review"
    REGIMEN_ITEMS ||--o{ REMINDER_SCHEDULES : "có lịch"
    REMINDER_SCHEDULES ||--o{ SCHEDULE_ELIGIBILITY_CHECKS : "được kiểm tra"
    SAFETY_ASSESSMENTS o|--o{ SCHEDULE_ELIGIBILITY_CHECKS : "cung cấp kết quả"
    HCP_REVIEWS o|--o{ SCHEDULE_ELIGIBILITY_CHECKS : "cung cấp quyết định"
    REMINDER_SCHEDULES ||--o{ REMINDER_EVENTS : "phát sinh"
    REGIMEN_ITEMS ||--o{ ADHERENCE_RECORDS : "có tuân thủ"
    REMINDER_EVENTS o|--o{ ADHERENCE_RECORDS : "được phản hồi"
    USERS ||--o{ ADHERENCE_RECORDS : "ghi nhận"
```

Một eligibility check có thể không cần HCP review, nhưng phải tham chiếu đúng phiên bản lịch và assessment phù hợp. Gửi reminder không đồng nghĩa patient đã dùng thuốc.

