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

        # Pre-fetch UI IDs upfront before opening DB transaction block to avoid IO within active transaction
        ui_ids = []
        for _ in range(len(data.items)):
            try:
                res = await get_ui_id(shop_id=data.shop_id)
                ui_str = f"{res.get('prefix')}-{res.get('current_number')}" if isinstance(res, dict) else f"STM-{generate_uuid()[:6].upper()}"
            except Exception:
                ui_str = f"STM-{generate_uuid()[:6].upper()}"
            ui_ids.append(ui_str)

        # 1. Save to Primary DB
        async with AsyncInventoryLocalSession() as session:
            repo = StockMovAdjRepo(session)
            ic(data.date)
            date_val = data.date
            if isinstance(date_val, str):
                date_val = datetime.datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            elif not date_val:
                date_val = datetime.datetime.now(datetime.timezone.utc)

            shop_id = data.shop_id
            adj_type = data.type.value if hasattr(data.type, 'value') else data.type
            description = data.description or f"Stock adjusted via {adj_type}"

            item_infos = {
                'total_adjustment_items': 0,
                'total_adjustment_increment_stocks': 0,
                'total_adjustment_decrement_stocks': 0,
            }

            stock_mov_adj_models = []
            stockmovadj_items_toadd = []
            read_models = []

            for idx, item in enumerate(data.items):
                ic(item)
                single_stock_mov_adj_id = generate_uuid()
                item_id = generate_uuid()
                single_ui_id = ui_ids[idx]

                stock_mov_adj_models.append(StockMovementAdjustment(
                    id=single_stock_mov_adj_id,
                    ui_id=single_ui_id,
                    shop_id=data.shop_id,
                    type=adj_type,
                    description=description,
                    additional_infos={}
                ))

                stockmovadj_items_toadd.append(StockMovAdjItems(
                    id=item_id,
                    stock_move_adj_id=single_stock_mov_adj_id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    batch_id=item.batch_id,
                    serial_numbers=item.serial_numbers or [],
                    type=item.type.value,
                    stocks=item.stocks,
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

                single_product = StockMovementProduct(
                    product_id=item.product_id,
                    ui_id=item.ui_id,
                    name=item.name,
                    stock_infos={
                        'stocks': item.stocks,
                        'stocks_after': item.stocks_after,
                        'stocks_before': item.stocks_before
                    },
                    type=item.type.value,
                    variant_infos=variant_info,
                    batch_infos=batch_info,
                    serial_numbers=item.serial_numbers,
                    category_infos={
                        'id': item.category_id,
                        'name': item.category_name,
                    },
                    unit_infos={
                        'id': item.unit_id,
                        'name': item.unit_name
                    }
                )

                single_item_infos = {
                    'total_adjustment_items': 1,
                    'total_adjustment_increment_stocks': item.stocks if item.type.value == "INCREMENT" else 0,
                    'total_adjustment_decrement_stocks': item.stocks if item.type.value == "DECREMENT" else 0,
                }

                adjjusted_date = date_val
                if isinstance(adjjusted_date, str):
                    adjjusted_date = datetime.datetime.strptime(adjjusted_date, "%Y-%m-%d").date()

                read_models.append(StockMovementReadModel(
                    stock_movement_id=single_stock_mov_adj_id,
                    ui_id=single_ui_id,
                    shop_id=data.shop_id,
                    movement_type=adj_type,
                    adjusted_date=adjjusted_date,
                    description=description,
                    item_infos=single_item_infos,
                    products=[single_product]
                ))

            ic("before create_bulk_adjustment")
            await repo.create_bulk_adjustment(stock_mov_adj_models)
            ic("after create_bulk_adjustment")

            ic("before create_bulk_items")
            await repo.create_bulk_items(stockmovadj_items_toadd)
            ic("after create_bulk_items")

            ic("before commit")
            await session.commit()
            ic("after commit")
            
            # await session.commit()

        ic("before read db")

        for read_model in read_models:
            ic("creating read model")
            await StockMovementReadDbRepo.create_stock_movement(read_model)
            ic("created read model")

        ic("after read db")

        return {"success": True, "ids":[]}
