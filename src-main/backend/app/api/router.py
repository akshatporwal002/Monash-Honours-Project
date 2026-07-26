from fastapi import APIRouter

from app.api.routes import health, materials, retrieval, students

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(students.router, tags=["student learning"])
api_router.include_router(materials.router, tags=["learning materials"])
api_router.include_router(retrieval.router, tags=["retrieval"])
