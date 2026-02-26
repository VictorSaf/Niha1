from fastapi import FastAPI

from app.api.agents import router as agents_router
from app.api.health import router as health_router

app = FastAPI(title="Agent Control Plane", version="0.1.0")
app.include_router(health_router)
app.include_router(agents_router)
