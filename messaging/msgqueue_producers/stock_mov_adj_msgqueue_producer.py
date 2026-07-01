from ..main import RabbitMQMessagingConfig
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.repos.stock_mov_adj_repo import StockMovAdjRepo
from infras.read_db.repos.stock_movement_repo import StockMovementReadDbRepo
from infras.read_db.models.stock_movement_model import StockMovementReadModel, StockMovementProduct, VariantInfo, BatchInfo, SerialInfo
from infras.primary_db.models.stock_mov_adj_model import StockMovementAdjustment, StockMovAdjItems
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
import datetime
from integrations.utility_service import get_ui_id, get_shop_category, get_shop_unit


class MessagingQueueStockMovAdjProducer:

    def __init__(self,headers:dict,payload:dict,saga_datas:dict):
        self.headers=headers
        self.payload=payload
        self.saga_datas=saga_datas


    async def create_adjustment(self):
        ic(self.headers,self.payload,self.saga_datas)
        rabbitmq_connection=RabbitMQMessagingConfig()
        datas=self.saga_datas["data"]
        stock_mov_adj_data=datas['stock_mov_adj']
        execution=self.saga_datas['execution']
        current_step=execution['step']

        ic(execution,current_step,stock_mov_adj_data)


        # STEP-1: Handled PRODUCT_VERIFY results
        if current_step == "PRODUCT_VERIFY_UPDATE":
            ic("INSIDE PRODUCT_VERIFY_UPDATE")
            
            product_ids = []
            for itm in stock_mov_adj_data['items']:
                product_ids.append(itm['product_id'])

            routing_key="products.service.routing.key"
            exchange_name="products.service.exchange"
            entity_name="get_bulk_product_by_id"
            service_name="PRODUCTS"

            headers={
                **self.headers,
                "routing_key":routing_key,
                "exchange_name":exchange_name,
                "entity_name":entity_name,
                "service_name":service_name,
                "body": {
                    "shop_id":stock_mov_adj_data['shop_id'],
                    "id":list(set(product_ids))
                }
            }

            await rabbitmq_connection.publish_event(
                routing_key=routing_key,
                payload=self.payload,
                headers=headers,
                exchange_name=exchange_name
            )

            return {
                "success":True,
                "execution":{
                    "step":"FETCHING_PPRODUCTS",
                    "service":"PRODUCTS"
                }
            }


        # STEP-2: CREATE STOCK MOVEMENT
        if current_step == "FETCHING_PPRODUCTS":
            ic("INSIDE FETCHING PRODUCTS")
            ic("Final step: FETCHING_PRODUCTS - saving to DBs")

            stock_mov_adj_id = generate_uuid()
            ui_id_res=await get_ui_id(shop_id=stock_mov_adj_data['shop_id'])
            ui_id=f"{ui_id_res.get("prefix")}-{ui_id_res.get("current_number")}"
            # 1. Primary DB Insert
            async with AsyncInventoryLocalSession() as session:
                repo = StockMovAdjRepo(session)

                date_val = stock_mov_adj_data.get('date')
                if isinstance(date_val, str):
                    date_val = datetime.datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                elif not date_val:
                    date_val = datetime.datetime.now(datetime.timezone.utc)

                stock_mov_adj_model = StockMovementAdjustment(
                    id=stock_mov_adj_id,
                    ui_id=ui_id,
                    shop_id=stock_mov_adj_data['shop_id'],
                    type=stock_mov_adj_data.get('type'),
                    description=stock_mov_adj_data.get('description'),
                    additional_infos={
                        "date":date_val.isoformat() if isinstance(date_val, datetime.datetime) else date_val
                    }

                )

                await repo.create_bulk_adjustment([stock_mov_adj_model])

                items_models = []
                read_db_products = []

                fetched_products_data = datas.get('products', {})
                ic(fetched_products_data)
                if isinstance(fetched_products_data, dict):
                    fetched_products = fetched_products_data.get('products', [])
                    fetched_variants = fetched_products_data.get('variants', [])
                elif isinstance(fetched_products_data, list):
                    fetched_products = fetched_products_data
                    fetched_variants = []
                else:
                    fetched_products = []
                    fetched_variants = []

                total_items = len(stock_mov_adj_data['items'])
                total_quantity = 0

                for item in stock_mov_adj_data['items']:
                    ic(item)
                    item_id = generate_uuid()
                    serial_numbers = []
                    if item.get('serialno_infos'):
                        serial_numbers = [{"id": s.get('id'), "name": s.get('name')} for s in item['serialno_infos']]

                    stock_quantity = item.get("qty")
                    total_quantity += stock_quantity

                    ic(stock_quantity)
                    ic(total_quantity)

                    current_stocks = 0
                    product_fetched_info = next((p for p in fetched_products if p['id'] == item['product_id']), {})
                    inventory_units = product_fetched_info.get('inventory_units', [])
                    item_batch_id = item.get('batch_id')
                    item_variant_id = item.get('variant_id')
                    
                    for iu in inventory_units:
                        iu_batch_id = (iu.get('batch_infos') or {}).get('id')
                        iu_variant_id = (iu.get('variant_infos') or {}).get('id')
                        if iu_batch_id == item_batch_id and iu_variant_id == item_variant_id:
                            if iu.get('stock_infos'):
                                current_stocks = iu.get('stock_infos').get('physical_stocks', 0)
                            break
                    ic(current_stocks)
                    stock_type = item.get('type', 'INCREMENT')
                    if stock_type == "INCREMENT":
                        stocks_after = current_stocks
                        stocks_before = current_stocks - stock_quantity
                    elif stock_type == "DECREMENT":
                        stocks_after = current_stocks
                        stocks_before = current_stocks + stock_quantity
                    else:
                        stocks_after = current_stocks
                        stocks_before = current_stocks - stock_quantity

                    items_models.append(StockMovAdjItems(
                        id=item_id,
                        stock_move_adj_id=stock_mov_adj_id,
                        product_id=item['product_id'],
                        variant_id=item.get('variant_id'),
                        batch_id=item.get('batch_id'),
                        serial_numbers=serial_numbers,
                        type=item.get('type'),
                        stocks=stock_quantity,
                        stocks_after=stocks_after,
                        stocks_before=stocks_before
                    ))

                    variant_fetched_info = next((v for v in fetched_variants if v['id'] == item.get('variant_id')), {})

                    variant_info = None
                    if item.get('variant_id'):
                        variant_info = VariantInfo(
                            variant_id=item['variant_id'],
                            variant_name=variant_fetched_info.get('name', 'Unknown')
                        )
                        
                    batch_info = None
                    if item.get('batch_id'):
                        b_infos = item.get('batch_infos', {})
                        
                        mfg_date = None
                        if b_infos.get('manufacturing_date'):
                            mfg_date = datetime.datetime.fromisoformat(b_infos.get('manufacturing_date').replace("Z", "+00:00"))

                        exp_date = None
                        if b_infos.get('expiry_date'):
                            exp_date = datetime.datetime.fromisoformat(b_infos.get('expiry_date').replace("Z", "+00:00"))

                        batch_info = BatchInfo(
                            batch_id=item['batch_id'],
                            batch_name=b_infos.get('name', 'Unknown'),
                            mfg_date=mfg_date,
                            exp_date=exp_date
                        )

                    serial_info = None
                    if serial_numbers:
                        serial_info = SerialInfo(
                            serialno_id="bulk_serials",
                            serial_numbers=[s['name'] for s in serial_numbers]
                        )

                    category_id = product_fetched_info.get('category_id')
                    unit_id = product_fetched_info.get('unit_id')
                    category_name = ""
                    unit_name = ""
                    if category_id:
                        cat_res = await get_shop_category(shop_id=stock_mov_adj_data['shop_id'], category_id=category_id)
                        category_name = cat_res.get("name", "") if isinstance(cat_res, dict) else ""
                    if unit_id:
                        unit_res = await get_shop_unit(shop_id=stock_mov_adj_data['shop_id'], unit_id=unit_id)
                        unit_name = unit_res.get("name", "") if isinstance(unit_res, dict) else ""

                    read_db_products.append(StockMovementProduct(
                        inventory_id=item['product_id'],
                        ui_id=product_fetched_info.get("ui_id", ""),
                        name=product_fetched_info.get("name", "Unknown"),
                        category_name=category_name,
                        unit_name=unit_name,
                        stocks_before=stocks_before,
                        stocks_adjusted=stock_quantity,
                        stocks_after=stocks_after,
                        type=item.get('type'),
                        variant=variant_info,
                        batch=batch_info,
                        serial_info=serial_info,
                        storage_location=item.get('storage_location_infos', {}).get('name', 'Default')
                    ))

                await repo.create_bulk_items(items_models)

                await session.commit()
            
            # 2. Read DB Insert
            date_val = stock_mov_adj_data.get('date')
            if isinstance(date_val, str):
                date_val = datetime.datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            elif not date_val:
                date_val = datetime.datetime.now(datetime.timezone.utc)

            read_model = StockMovementReadModel(
                stock_movement_id=stock_mov_adj_id,
                ui_id=ui_id,
                shop_id=stock_mov_adj_data['shop_id'],
                movement_type=stock_mov_adj_data.get('type'),
                adjusted_date=date_val,
                description=stock_mov_adj_data.get('description', ''),
                total_items=total_items,
                total_quantity=total_quantity,
                products=read_db_products
            )
            await StockMovementReadDbRepo.add_updatereaddb(read_model)

            try:
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": stock_mov_adj_data.get('shop_id'),
                        "user_name": "siva",
                        "service": "StockAdjustment",
                        "action": "CREATE",
                        "entity_type": "StockAdjustment",
                        "entity_id": stock_mov_adj_id,
                        "description": f"Created stock movement adjustment",
                        "changes": [{"field": "id", "before": "", "after": str(stock_mov_adj_id)}]
                    },
                    headers={}
                )
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")

            return {
                "success": True,
                "execution": None
            }

        