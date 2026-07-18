from fastapi import APIRouter

from app.api.v1.routes import auth, health, projects, runs, work_items

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(work_items.router, prefix="/work-items", tags=["work-items"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
