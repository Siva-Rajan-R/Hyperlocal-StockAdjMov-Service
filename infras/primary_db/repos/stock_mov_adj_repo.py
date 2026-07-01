from models.repo_models.base_repo_model import BaseRepoModel
from models.service_models.base_service_model import BaseServiceModel
from sqlalchemy import select,update,delete,func,or_,and_,String,case,literal,literal_column,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload,load_only
from ..models.stock_mov_adj_model import StockMovAdjItems,StockMovementAdjustment
from schemas.v1.stock_mov_adj_schemas.db_schemas import CreateStockMovAdjDbSchema,CreateStockMovAdjItemsDbSchema,DeleteStockMovAdjDbSchema
from schemas.v1.stock_mov_adj_schemas.request_schema import GetAllStockMovAdjSchemas,GetStockMovAdjByIdSchema,GetStockMovAdjByShopIdSchema
from sqlalchemy.dialects.postgresql import insert
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from typing import Optional,List
from icecream import ic
from core.data_formats.enums.stock_mov_adj_enums import StockMovAdjTypeEnums,StockMovAdjItemTypeEnums



class StockMovAdjRepo:
    def __init__(self, session:AsyncSession):
        self.session=session
        self.stockmovadj_cols=(
            StockMovementAdjustment.id,
            StockMovementAdjustment.shop_id,
            StockMovementAdjustment.type,
            StockMovementAdjustment.sequence_id,
            StockMovementAdjustment.ui_id,
            StockMovementAdjustment.description,
            StockMovementAdjustment.created_at,
            StockMovementAdjustment.updated_at
        )

        self.item_cols=(
           StockMovAdjItems.id,
           StockMovAdjItems.product_id,
           StockMovAdjItems.variant_id,
           StockMovAdjItems.batch_id,
           StockMovAdjItems.serial_numbers,
           StockMovAdjItems.stocks,
           StockMovAdjItems.type,
           StockMovAdjItems.stocks_before,
           StockMovAdjItems.stocks_after,
        )

    @start_db_transaction
    async def get_next_sequence(self, shop_id: str, start_from: int) -> int:
        from sqlalchemy import text
        seq_name = f"seq_purchase_{shop_id.replace('-', '_').lower()}"
        await self.session.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START WITH {start_from}"))
        res = await self.session.execute(text(f"SELECT nextval('{seq_name}')"))
        return res.scalar_one()

    @start_db_transaction
    async def create_bulk_adjustment(self,data:List[StockMovementAdjustment]):
        if data:
            self.session.add_all(data)
        return True
    
    @start_db_transaction
    async def create_bulk_items(self,data:List[StockMovAdjItems]):
        if data:
            self.session.add_all(data)
        return True
    
    
    @start_db_transaction
    async def delete_adjustment(self,data:DeleteStockMovAdjDbSchema):
        stmt=(
            delete(
                StockMovementAdjustment
            )
            .where(
                StockMovementAdjustment.id==data.id,
                StockMovementAdjustment.shop_id==data.shop_id
            )
            .returning(*self.stockmovadj_cols)
        )

        res=(await self.session.execute(stmt)).mappings().all()
        ic(res)
        return res
    
    async def get_movements(self,data:GetAllStockMovAdjSchemas):
        offset=data.offset-1 if data.offset>0 else 0
        cursor=offset*data.limit

        stmt = (
            select(StockMovementAdjustment)
            .options(
                load_only(
                    *self.stockmovadj_cols
                ),

                selectinload(StockMovementAdjustment.items)
                .load_only(
                    *self.item_cols
                )
            )
        )

        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res
    
    async def get_movements_by_shop_id(self,data:GetStockMovAdjByShopIdSchema):
        offset=data.offset-1 if data.offset>0 else 0
        cursor=offset*data.limit

        stmt = (
            select(StockMovementAdjustment)
            .options(
                load_only(
                    *self.stockmovadj_cols
                ),

                selectinload(StockMovementAdjustment.items)
                .load_only(
                    *self.item_cols
                )
            )
            .where(
                StockMovementAdjustment.shop_id==data.shop_id
            )
        )

        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res
    

    async def get_movement_by_id(self,data:GetStockMovAdjByIdSchema):

        stmt = (
            select(StockMovementAdjustment)
            .options(
                load_only(
                    *self.stockmovadj_cols
                ),

                selectinload(StockMovementAdjustment.items)
                .load_only(
                    *self.item_cols
                )
            )
            .where(
                StockMovementAdjustment.shop_id==data.shop_id,
                StockMovementAdjustment.id==data.id
            )
        )

        res = (await self.session.execute(stmt)).scalars().one_or_none()
        ic(res)
        return res


    
    
