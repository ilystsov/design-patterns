from fastapi import APIRouter

from server import contracts

router = APIRouter()


@router.get("/parents", response_model=contracts.Message)
async def find_parent() -> contracts.Message:
    return contracts.Message(message='found parents')
