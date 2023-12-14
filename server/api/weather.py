from fastapi import APIRouter

from server import contracts

router = APIRouter()


@router.get("/weather", response_model=contracts.Message)
async def weather_report() -> contracts.Message:
    return contracts.Message(message='weather report')
