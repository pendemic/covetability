from fastapi import FastAPI

from app.api.admin import router as admin_router

app = FastAPI(title="Covetability Pipeline", version="0.1.0")
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
