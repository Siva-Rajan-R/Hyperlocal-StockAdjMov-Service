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

            user_info = getattr(data, 'user_info', None) or (data.get('user_info') if isinstance(data, dict) else None) or getattr(data, 'user_infos', None) or (data.get('user_infos') if isinstance(data, dict) else None) or {}
            added_by = getattr(data, 'added_by', None) or (data.get('added_by') if isinstance(data, dict) else None)
            
            # If not in top-level, check in items
            if (not user_info or not added_by or added_by == "System") and data.items:
                for itm in data.items:
                    itm_u = getattr(itm, 'user_info', None) or (itm.get('user_info') if isinstance(itm, dict) else None) or getattr(itm, 'user_infos', None) or (itm.get('user_infos') if isinstance(itm, dict) else None)
                    if itm_u and isinstance(itm_u, dict) and (itm_u.get('email') or itm_u.get('name') or itm_u.get('user_id')):
                        user_info = itm_u
                    itm_added = getattr(itm, 'added_by', None) or (itm.get('added_by') if isinstance(itm, dict) else None)
                    if itm_added and str(itm_added).strip() not in ("System", ""):
                        added_by = itm_added
                    if user_info and added_by and added_by != "System":
                        break

            user_id = getattr(data, 'user_id', None) or (data.get('user_id') if isinstance(data, dict) else None) or user_info.get('user_id') or user_info.get('id')
            user_name = getattr(data, 'user_name', None) or (data.get('user_name') if isinstance(data, dict) else None) or user_info.get('name') or user_info.get('user_name')
            user_email = getattr(data, 'user_email', None) or (data.get('user_email') if isinstance(data, dict) else None) or user_info.get('email')
            user_role = getattr(data, 'user_role', None) or (data.get('user_role') if isinstance(data, dict) else None) or user_info.get('role')

            if not added_by or added_by == "System":
                if not user_name and user_email:
                    user_name = user_email.split("@")[0]
                final_user = user_name or "System"
                if user_email and final_user != user_email and f"- {user_email}" not in final_user:
                    added_by = f"{final_user} - {user_email}"
                elif user_email and not user_name:
                    added_by = user_email
                elif user_name:
                    added_by = user_name
                else:
                    added_by = "System"

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

                item_val_type = item.type.value if hasattr(item.type, 'value') else item.type
                item_entity_name = getattr(item, 'entity_name', None) or (item.get('entity_name') if isinstance(item, dict) else None)
                if not item_entity_name:
                    if "EXCHANGE" in str(adj_type).upper():
                        if item_val_type == "DECREMENT":
                            item_adj_type = "ONLINE_EXCHANGE" if "ONLINE" in str(adj_type).upper() else "OFFLINE_EXCHANGE"
                        else:
                            item_adj_type = "ONLINE_SALES_EXCHANGE" if "ONLINE" in str(adj_type).upper() else "OFFLINE_SALES_EXCHANGE"
                    else:
                        item_adj_type = adj_type
                else:
                    item_adj_type = item_entity_name

                item_description = getattr(item, 'description', None) or (item.get('description') if isinstance(item, dict) else None)
                if (
                    not item_description
                    or ("Stock increase via" in item_description and item_val_type == "DECREMENT")
                    or ("Stock decrease via" in item_description and item_val_type == "INCREMENT")
                    or (getattr(item, 'ui_id', None) and f"({getattr(item, 'ui_id')})" in item_description)
                ):
                    item_entity_id = (
                        getattr(item, 'order_ui_id', None) or (item.get('order_ui_id') if isinstance(item, dict) else None) or
                        getattr(item, 'sale_ui_id', None) or (item.get('sale_ui_id') if isinstance(item, dict) else None) or
                        getattr(item, 'entity_id', None) or (item.get('entity_id') if isinstance(item, dict) else None) or
                        getattr(data, 'order_ui_id', None) or (data.get('order_ui_id') if isinstance(data, dict) else None) or
                        getattr(data, 'sale_ui_id', None) or (data.get('sale_ui_id') if isinstance(data, dict) else None) or
                        getattr(data, 'entity_id', None) or (data.get('entity_id') if isinstance(data, dict) else None)
                    )
                    if item_entity_id == getattr(item, 'ui_id', None):
                        item_entity_id = (
                            getattr(data, 'order_ui_id', None) or (data.get('order_ui_id') if isinstance(data, dict) else None) or
                            getattr(data, 'sale_ui_id', None) or (data.get('sale_ui_id') if isinstance(data, dict) else None) or
                            getattr(data, 'entity_id', None) or (data.get('entity_id') if isinstance(data, dict) else None)
                        )
                        if item_entity_id == getattr(item, 'ui_id', None):
                            item_entity_id = None

                    desc_entity = item_adj_type.replace("_", " ").lower() if item_adj_type else "adjustment"
                    desc_entity = desc_entity.replace("offline ", "").replace("online ", "").strip()
                    if item_val_type == "INCREMENT":
                        action_text = "Stock increase"
                    elif item_val_type == "DECREMENT":
                        action_text = "Stock decrease"
                    else:
                        action_text = "Stock adjusted"
                    item_description = f"{action_text} via {desc_entity} ({item_entity_id})" if item_entity_id else f"{action_text} via {desc_entity}"

                stock_mov_adj_models.append(StockMovementAdjustment(
                    id=single_stock_mov_adj_id,
                    ui_id=single_ui_id,
                    shop_id=data.shop_id,
                    type=item_adj_type,
                    description=item_description,
                    additional_infos={"added_by": added_by, "user_id": user_id, "user_info": user_info}
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
                    movement_type=item_adj_type,
                    adjusted_date=adjjusted_date,
                    description=item_description,
                    item_infos=single_item_infos,
                    products=[single_product],
                    added_by=added_by,
                    user_id=user_id,
                    user_name=user_name,
                    user_email=user_email,
                    user_role=user_role,
                    user_info=user_info
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

        try:
            from ..main import RabbitMQMessagingConfig
            rabbitmq_connection = RabbitMQMessagingConfig()
            analytics_payload = {
                "shop_id": data.shop_id,
                "entity_name": "STOCK_MOVEMENT",
                "entity_id": str(""),
                "action": "CREATE"
            }
            await rabbitmq_connection.publish_event(
                routing_key="analytics.service.routing.key",
                exchange_name="analytics.service.exchange",
                payload=analytics_payload,
                headers={
                    "entity_name": "stockmovadj_event",
                    "service_name": "ANALYTICS",
                    "saga_id": "none",
                    "reply_key": "none",
                    "reply_exchange": "none",
                    "reply_entity_name": "none",
                    "body": analytics_payload
                }
            )
        except Exception as e:
            ic(f"Failed to publish analytics event from service: {e}")

        return {"success": True, "ids":[]}
