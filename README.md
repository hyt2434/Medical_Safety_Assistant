# Medication Safety Assistant

Vietnamese medication intake, reference lookup and interaction assessment. Intake
confirmation verifies transcription; it does not establish medication identity or
clinical safety.

## Kiểm tra UI trên branch tích hợp

Branch `integration/ui-intake-dev` hợp nhất `origin/dev` (`1268b73c`) và
`NLP-ChatBot` (`451be27c`). UI dùng `apps/frontend`; API dùng `apps/backend/api`,
Auth dùng `src/shared/auth`, module nghiệp vụ dùng `src/`. Bản backend cũ trong
`apps/backend/src` đã được hợp nhất, không chạy song song hai bộ API.

Tại gốc worktree, chạy bằng Python đã cài `requirements.txt`:

```powershell
python scripts/preview-ui.py
```

Lệnh mở frontend tại `http://127.0.0.1:5173`, backend tại cổng 8000; `Ctrl+C`
dừng cả hai. Có thể chọn `--port` và `--api-port` nếu cổng đang bận. Auth preview
dùng riêng `artifacts/auth/ui-preview.sqlite`, không dùng database Auth đang có.
Chạy `npm.cmd ci` trong `apps/frontend` trước nếu chưa có dependencies.

Tài khoản local để kiểm tra: `mai.demo@example.com` / `Mai-patient-2026`.
Các tài khoản HCP/admin và role khác nằm trong [backend README](apps/backend/README.md).

Kiểm tra `/login` → `/dashboard` → `/intake` hoặc `/chat`, cùng các trang HCP/admin.
Để **lưu bản nháp và đánh giá thật**, cần cấu hình `CORE_DB_DSN`,
`CORE_REFERENCE_BUILD`, cấp UUID của tài khoản preview vào Core theo
[hợp đồng Auth/Core](db/auth/README.md), và chuẩn bị Qwen/Ollama, Whisper,
Tesseract cùng DDInter index. Nếu chưa cấu hình, UI báo không có liên kết Core
và không cho lưu; không thay kết quả thật bằng dữ liệu mẫu. Launcher không tự
migrate hoặc nạp dữ liệu Core. HCP review, hồ sơ và lịch nhắc vẫn là prototype.

Trong Intake: chọn nguồn → nhập/upload → sửa và **Lưu thay đổi** từng thuốc →
đồng ý xác nhận → **Xác nhận danh sách** → **Nhận diện và đánh giá tương tác**.
Gợi ý tên thuốc/cách trình bày chỉ thay form sau khi người dùng chọn; có thể
hoàn tác trước khi lưu. Sau khi lưu, Core giữ phiên bản entry mới, không dùng
lịch sử chỉnh sửa trong sessionStorage của prototype cũ.

Kiểm thử UI: `npm.cmd run test:e2e` trong `apps/frontend`; đặt `E2E_PYTHON`
đến Python có dependencies. Auth test dùng SQLite riêng; Intake thường dùng
HTTP fixtures để kiểm tra hợp đồng UI/API. Bài `intake-real.spec.ts` chỉ chạy
khi có đủ database test và model thật, xem [hướng dẫn frontend](apps/frontend/README.md).

| Path | Responsibility |
| --- | --- |
| `apps/frontend/` | Canonical React/TypeScript UI, Auth client and OCR review flow. |
| `apps/backend/` | Auth/RBAC and Core V4 Intake HTTP API. |
| `src/module1_intake/` | Intake adapters, OCR and the layered NLP MVP V2. |
| `src/module2_medications/` | Medication identification and reference services. |
| `src/module3_interactions/` | Interaction assessment and official-source adapters. |
| `src/module4_hcp/`, `src/module5_reminders/` | Existing package contracts for future HCP/reminder services. |
| `src/shared/` | Shared intake contracts, import utilities and Core V4 application adapters. |
| `db/` | Canonical Core Database V4 migrations, management tools, contracts and DB tests. |
| `data/` | Approved original/processed medication data and documentation; preserve source bytes. |
| `docs/` | Project requirements, design and management; `docs/pa/` holds submission sources and deliverables. |
| `tests/` | Unit, integration and end-to-end coverage; DB-specific tests remain in `db/tests/`. |
| `scripts/` | Shared setup, data provisioning, CLI and test utilities. |
| `artifacts/` | Ignored local runtimes, databases, caches, manifests and development evidence. |

Start with the [NLP setup and launchers](src/module1_intake/nlp/README.md),
[frontend DTO/API contract](src/module1_intake/nlp/API.md), and
[Core V4 setup](db/README.md). NLP uses structured-first Q&A and local BM25 document
retrieval. Backend/UI adapters import `module1_intake.nlp.interfaces.application`;
implementation imports use the canonical layer folders. Root compatibility
wrappers have been removed; launchers live in `scripts/nlp/`.

Run the [canonical React frontend](apps/frontend/README.md) with `npm ci` and
`npm run dev` from `apps/frontend/`. The original team-authored
[React PA1 prototype](docs/pa/pa1/react-prototype/README.md) remains independently
runnable with its unique speech/chat behavior, assets and tests. Historical UI
implementations under `docs/pa/` belong to their submissions. The backend launcher
is `apps/backend/app.py`; reusable Python business modules live in root `src/`.
See [backend setup and Core bindings](apps/backend/README.md). Reports build from their own directories
and use canonical assets under `docs/design/` and `docs/pa/pa1/ui-prototype/screenshots/`.
Historical 35/64-table database diagrams describe earlier designs; Core V4 lives in `db/`.
`src/shared/schema.sql` is the separate SQLite DAV import staging schema.

Offline NLP regression command, from the repository root with `.venv` ready:

```powershell
& ./scripts/nlp/test_mvp.ps1 -Dsn ''
```

Persisted tests require an explicitly marked isolated database. Keep local DSNs,
credentials, environments and runtime evidence out of Git. The six approved CSVs
live only under `data/datasets/` and are versioned; other local datasets stay ignored.
See the [cleanup verification and known blockers](docs/management/repository-cleanup-2026-11-10.md).
