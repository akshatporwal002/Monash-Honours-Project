from fastapi import APIRouter

from app.api.routes import health, materials, retrieval, students, task_generation

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(students.router, tags=["student learning"])
api_router.include_router(materials.router, tags=["learning materials"])
api_router.include_router(retrieval.router, tags=["retrieval"])
api_router.include_router(task_generation.router, tags=["task generation"])
