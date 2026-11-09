"""Medical Safety Assistant backend entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.ocr import router as ocr_router

app = FastAPI(title="Medical Safety Assistant API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ocr_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
