from fastapi import FastAPI

from app.routers.webhooks import router as webhook_router

app = FastAPI(title="WebhookAI", version="0.1.0")
app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
