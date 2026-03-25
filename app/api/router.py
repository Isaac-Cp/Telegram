from fastapi import APIRouter

from app.api.routes import contacts, conversations, dashboard, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(contacts.router, prefix="/api/v1", tags=["contacts"])
api_router.include_router(conversations.router, prefix="/api/v1", tags=["conversations"])
api_router.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])

