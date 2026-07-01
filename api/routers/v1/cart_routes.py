from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated, Optional
import httpx
from datetime import datetime, timezone, timedelta
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict, BaseResponseTypDict, ErrorResponseTypDict
from infras.caching.models.cart_model import StockAdjustmentCartCacheModel
from schemas.v1.stock_mov_adj_schemas.request_schema import EventCreateStockMovAdjSchema
from ...handlers.stock_mov_adj_handler import HandleStockMovAdjRequest
from infras.primary_db.main import AsyncSession, get_pg_async_session
from pydantic import BaseModel
from icecream import ic
from integrations.stocks_reservation import commit_reservation,remove_reservation_item,cancel_reservation,create_reservation
from schemas.v1.stock_mov_adj_cart_schemas.request_schemas import CartCancelRequest,CartCompleteRequest,CartRemoveRequest,CartReserveRequest

router = APIRouter(
    tags=["Stock Adjustments Cart"],
    prefix="/stockmovadj/cart"
)


TTL_MINUTES = 3
ASYNC_PG_SESSION = Annotated[AsyncSession, Depends(get_pg_async_session)]



@router.get('/init')
async def init_cart():
    session_id = generate_uuid()
    cart = StockAdjustmentCartCacheModel(session_id)
    await cart.set_cart(items=[], ttl=TTL_MINUTES * 60)
    
    return SuccessResponseTypDict(
        detail=BaseResponseTypDict(
            status_code=200, 
            success=True, 
            msg="Cart session initialized successfully"
        ),
        data={"session_id": session_id}
    )

@router.post('/reserve')
async def reserve_item(data: CartReserveRequest):
    res=await create_reservation(data=data)
    ic(res)
    return SuccessResponseTypDict(detail=BaseResponseTypDict(status_code=200, success=True, msg="Item reserved and cart updated"))

@router.post('/cancel')
async def cancel_cart(data: CartCancelRequest):
    res=await cancel_reservation(data=data)
    ic(res)
    return SuccessResponseTypDict(detail=BaseResponseTypDict(status_code=200, success=True, msg="Cart session cancelled"))


@router.post('/remove')
async def remove_item(data: CartRemoveRequest):
    res=await remove_reservation_item(data=data)
    ic(res)
    return SuccessResponseTypDict(detail=BaseResponseTypDict(status_code=200, success=True, msg="Item removed from cart and reservation released"))

# @router.post('/complete')
# async def complete_cart(data: CartCompleteRequest, session: ASYNC_PG_SESSION):

#     await commit_reservation(session_id=data.session_id)

#     return SuccessResponseTypDict(detail=BaseResponseTypDict(status_code=200, success=True, msg="Stock adjustments completed successfully"))
