# Remediation plan

## Đã triển khai trong đợt audit

| ID | Priority | Thay đổi | Regression |
|---|---|---|---|
| SEC-01 | High | Seed không phục hồi role permission đã bị gỡ | removed_permission_stays_removed_after_restart |
| SEC-02 | High | Budget đăng nhập persistent theo account và peer, 429 + Retry-After; migration auth_002 | login_throttle_persists_across_restart; rate_limit_peer_cannot_be_bypassed_with_forwarded_headers |
| SEC-03 | Medium | Token rotation khi switch context, không kéo dài absolute expiry | context_rotation_rejects_replayed_old_token |
| SEC-04 | High | Hủy session khi grant mở rộng quyền/thời hạn | grant_cannot_upgrade_an_existing_stolen_session |
| SEC-05 | Medium | Fail closed khi thiếu Origin/Referer; xác minh Referer fallback; headers trên denial | csrf_missing_origin_rejected_even_with_cookie; csrf_origin_referer_and_cors |
| SEC-06 | High nếu deploy demo | Guard production + bỏ credential demo khỏi frontend production bundle | production_rejects_unsafe_config_and_existing_demo_users; build scan |
| SEC-07 | High tiềm năng theo dependency | Nâng security floor Pillow/Starlette/multipart/dotenv/AnyIO/Mako; kiểm tra trong venv riêng | clean install, full pytest, pip-audit |
| SEC-08 | Medium | Body cap trước multipart/JSON parsing; không trả stderr OCR trực tiếp | body_limit_precedes_json_and_multipart_parsing |

## Trước khi tiếp nhận dữ liệu thật / mở public

1. **Backend owner:** triển khai ownership/care relationship cho API clinical thực; không dùng các state frontend mô phỏng làm dữ liệu thật (SEC-09).
2. **Frontend/backend owners:** thay storage demo bằng API có scope; không giữ thông tin người dùng trước sau logout; bổ sung test đổi tài khoản cùng browser (SEC-09).
3. **Ops:** dùng môi trường sạch từ requirements đã vá; không tiếp tục deploy Python global cũ. Chốt lockfile/hash dependency và cập nhật định kỳ. Audit snapshot không đảm bảo các version tương lai.
4. **Ops:** AUTH_ENV=production, AUTH_SEED_DEMO=0, AUTH_COOKIE_SECURE=1, HTTPS allowlist chính xác; database không còn account demo. Reverse proxy cần TLS, HSTS, timeout, body/concurrency limits và trusted proxy policy.
5. **DB owner:** tách migration role và runtime DML role; backup/restore và retention audit; không đổi quyền Core V4 trong đợt này.
6. **Security owner:** tập trung audit denials, cảnh báo brute force, giới hạn/retention logs, MFA/reauth cho admin, idle timeout (SEC-10/11).
7. **OCR owner:** retention/encryption/ACL thư mục ảnh/text; không expose thư mục artifacts qua static server. Quyết định thời gian lưu và cách xóa dữ liệu trước production.
8. **DB owner:** kiểm kê FK/check constraints của database legacy và bổ sung bằng migration có backup; migration adoption hiện không tự rebuild bảng cũ (SEC-12).

## Lưu ý tương thích

- Postman/CLI gửi request ghi phải có `Origin` thuộc `AUTH_ALLOWED_ORIGINS` (ví dụ `http://127.0.0.1:5173`); header không thay thế session cookie.
- Switch-context đổi cookie; client phải giữ cookie mới. Grant mở rộng quyền yêu cầu người được cấp quyền đăng nhập lại.
- Permission mặc định của role đã tồn tại không tự sửa sau restart. Muốn thêm permission cho role cũ cần migration/operational change có kiểm soát.
- Local demo vẫn có thể seed với AUTH_SEED_DEMO=1; production guard chỉ áp dụng khi khai báo AUTH_ENV=production. Không coi development mode là cấu hình production.
