import os

from fastapi import FastAPI

from app.health import router as health_router
from app.routers.webhooks import router as webhook_router

app = FastAPI(title="WebhookAI", version="0.1.0")
app.include_router(health_router)
app.include_router(webhook_router)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
