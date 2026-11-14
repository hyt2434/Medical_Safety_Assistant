"""Bound request bodies before multipart parsing, including chunked transfers."""
from starlette.responses import JSONResponse

class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, send)
        limit = 11 * 1024 * 1024 if scope["path"].startswith("/api/v1/ocr/") else 16 * 1024
        data = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data.extend(message.get("body", b""))
            if len(data) > limit:
                response = JSONResponse({"detail": "Dữ liệu gửi lên vượt giới hạn",
                    "error": {"code": "PAYLOAD_TOO_LARGE", "message": "Dữ liệu gửi lên vượt giới hạn"}},
                    status_code=413, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(data), "more_body": False}
        await self.app(scope, replay, send)
