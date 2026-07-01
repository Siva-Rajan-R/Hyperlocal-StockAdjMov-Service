from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from ...handlers.stock_mov_adj_handler import HandleStockMovAdjRequest
from fastapi import APIRouter,Query,Depends
from infras.primary_db.main import AsyncSession,get_pg_async_session
from typing import Optional,Annotated,List
from schemas.v1.stock_mov_adj_schemas.request_schema import CreateStockMovAdjSchema,DeleteStockMovAdjSchema,GetStockMovAdjByIdSchema,GetAllStockMovAdjSchemas,GetStockMovAdjByShopIdSchema


router=APIRouter(
    tags=["Stock Movements Crud's"],
    prefix="/stockmovadj"
)

SHOP_ID="37d5519b-51a1-5854-982b-4d6524171017"
ADDED_BY="siva-user"

ASYNC_PG_SESSION=Annotated[AsyncSession,Depends(get_pg_async_session)]

@router.post("")
async def create(data:CreateStockMovAdjSchema,session:ASYNC_PG_SESSION):
    return await HandleStockMovAdjRequest(session=session).create(data=data)


@router.delete("/{shop_id}/{id}")
async def delete(session:ASYNC_PG_SESSION,data:DeleteStockMovAdjSchema=Depends()):
    return await HandleStockMovAdjRequest(session=session).delete(data=data)


@router.get("")
async def get(session:ASYNC_PG_SESSION,data:GetAllStockMovAdjSchemas=Depends()):
    return await HandleStockMovAdjRequest(session=session).get_stock_movements(data=data)


@router.get("/by/shop/{shop_id}")
async def search(session:ASYNC_PG_SESSION, data:GetStockMovAdjByShopIdSchema=Depends()):
    return await HandleStockMovAdjRequest(session=session).get_stock_movements_by_shop_id(data=data)

@router.get("/by/id/{shop_id}/{id}")
async def get_supplier_stats(session:ASYNC_PG_SESSION,data:GetStockMovAdjByIdSchema=Depends()):
    return await HandleStockMovAdjRequest(session=session).get_stock_movements_by_id(data=data)