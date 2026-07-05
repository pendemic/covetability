from fastapi import APIRouter

from app.api.public.bags import router as bags_router
from app.api.public.evidence import router as evidence_router
from app.api.public.listings import router as listings_router
from app.api.public.market import router as market_router

router = APIRouter()
router.include_router(bags_router)
router.include_router(evidence_router)
router.include_router(market_router)
router.include_router(listings_router)
