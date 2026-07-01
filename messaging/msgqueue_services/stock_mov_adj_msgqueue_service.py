from typing import Union
from icecream import ic
import datetime

from infras.primary_db.main import AsyncInventoryLocalSession
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid

from infras.primary_db.repos.stock_mov_adj_repo import StockMovAdjRepo
from infras.primary_db.models.stock_mov_adj_model import StockMovementAdjustment, StockMovAdjItems

from infras.read_db.repos.stock_movement_repo import StockMovementReadDbRepo
from infras.read_db.models.stock_movement_model import StockMovementReadModel, StockMovementProduct, VariantInfo, BatchInfo, SerialInfo

from schemas.v1.stock_mov_adj_schemas.request_schema import EventCreateStockMovAdjSchema
from integrations.utility_service import get_ui_id

class MessagingQueueStockMovAdjService:

    async def create_adjustment(self, data: Union[EventCreateStockMovAdjSchema, dict]):
        if isinstance(data, dict):
            data = EventCreateStockMovAdjSchema(**data)

        ic("Received EventCreateStockMovAdjSchema:", data)

        stock_mov_adj_id = generate_uuid()
        ui_id_res = await get_ui_id(shop_id=data.shop_id)
        ui_id=f"{ui_id_res.get("prefix")}-{ui_id_res.get("current_number")}"

        # 1. Save to Primary DB
        async with AsyncInventoryLocalSession() as session:
            repo = StockMovAdjRepo(session)
            ic(data.date)
            date_val = data.date
            if isinstance(date_val, str):
                date_val = datetime.datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            elif not date_val:
                date_val = datetime.datetime.now(datetime.timezone.utc)

            stock_mov_adj_model = StockMovementAdjustment(
                id=stock_mov_adj_id,
                ui_id=ui_id,
                shop_id=data.shop_id,
                type=data.type.value,
                description=data.description,
                additional_infos={
                    "date": date_val.isoformat() if isinstance(date_val, datetime.datetime) else date_val
                }
            )

            await repo.create_bulk_adjustment([stock_mov_adj_model])

            items_models = []
            read_db_products = []

            total_items = len(data.items)
            total_quantity = 0

            for item in data.items:
                item_id = generate_uuid()
                
                total_quantity += item.stocks_adjusted

                items_models.append(StockMovAdjItems(
                    id=item_id,
                    stock_move_adj_id=stock_mov_adj_id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    batch_id=item.batch_id,
                    serial_numbers=item.serial_numbers or [],
                    type=item.type.value,
                    stocks=item.stocks_adjusted,
                    stocks_after=item.stocks_after,
                    stocks_before=item.stocks_before
                ))

                variant_info = None
                if item.variant_id:
                    variant_info = VariantInfo(
                        variant_id=item.variant_id,
                        variant_name=item.variant_name or 'Unknown'
                    )

                batch_info = None
                if item.batch_id:
                    batch_info = BatchInfo(
                        batch_id=item.batch_id,
                        batch_name=item.batch_name or 'Unknown',
                        mfg_date=item.mfg_date,
                        exp_date=item.exp_date
                    )

                serial_info = None
                if item.serial_numbers:
                    serial_info = SerialInfo(
                        serialno_id="bulk_serials",
                        serial_numbers=[sn.get("name", "Unknown") for sn in item.serial_numbers if isinstance(sn, dict)]
                    )

                read_db_products.append(StockMovementProduct(
                    inventory_id=item.product_id,
                    ui_id=item.ui_id,
                    name=item.name,
                    stocks_before=item.stocks_before,
                    stocks_adjusted=item.stocks_adjusted,
                    stocks_after=item.stocks_after,
                    type=item.type.value,
                    variant=variant_info,
                    batch=batch_info,
                    serial_info=serial_info
                ))

            await repo.create_bulk_items(items_models)

            await session.commit()

        # 2. Save to Read DB
        read_model = StockMovementReadModel(
            stock_movement_id=stock_mov_adj_id,
            ui_id=ui_id,
            shop_id=data.shop_id,
            movement_type=data.type.value,
            adjusted_date=date_val,
            description=data.description or '',
            total_items=total_items,
            total_quantity=total_quantity,
            products=read_db_products
        )
        
        await StockMovementReadDbRepo.create_stock_movement(read_model)

        return {"success": True, "id": stock_mov_adj_id}
