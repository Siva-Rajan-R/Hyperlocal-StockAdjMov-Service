from ..main import RabbitMQMessagingConfig
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.repos.stock_mov_adj_repo import StockMovAdjRepo
from infras.read_db.repos.stock_movement_repo import StockMovementReadDbRepo
from infras.read_db.models.stock_movement_model import StockMovementReadModel, StockMovementProduct, VariantInfo, BatchInfo, SerialInfo
from infras.primary_db.models.stock_mov_adj_model import StockMovementAdjustment, StockMovAdjItems
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
import datetime
from typing import Optional,List,Dict
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
                    "step":"FETCHING_PRODUCTS",
                    "service":"PRODUCTS"
                }
            }


        if current_step == "FETCHING_PRODUCTS":
            
            stock_mov_adj_id = generate_uuid()
            ui_id_res = await get_ui_id(shop_id=stock_mov_adj_data['shop_id'])
            ui_id = f"{ui_id_res.get('prefix')}-{ui_id_res.get('current_number')}"
            
            # Resolve and parse dates early to share across primary and read DB blocks
            date_val = stock_mov_adj_data.get('date')
            if isinstance(date_val, str):
                date_val = datetime.datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            elif not date_val:
                date_val = datetime.datetime.now(datetime.timezone.utc)

            shop_id = stock_mov_adj_data.get("shop_id")
            supplier_id = stock_mov_adj_data.get("supplier_id")
            adj_type = stock_mov_adj_data.get("type")
            description = stock_mov_adj_data.get("description") or ""

            item_infos = {
                'total_adjustment_items': 0,
                'total_adjustment_increment_stocks': 0,
                'total_adjustment_decrement_stocks': 0,
            }

            stockmoveadj_items = stock_mov_adj_data.get("items") or []
            
            validated_payload_map: Dict[str, List[dict]] = {}
            for stockmovadj in stockmoveadj_items:
                p_id = stockmovadj['product_id']
                if p_id not in validated_payload_map:
                    validated_payload_map[p_id] = []
                validated_payload_map[p_id].append(stockmovadj)

            stockmovadj_read_items = []
            stockmovadj_items_toadd = []

            async with AsyncInventoryLocalSession() as session:
                repo = repo = StockMovAdjRepo(session)
                fetched_products_data = datas.get('products', {})
                for prod_db in fetched_products_data:
                    ic(prod_db)
                    product_id = prod_db['id']
                    product_name = prod_db['name']
                    db_ui_id = prod_db['ui_id']
                    
                    type_infos = prod_db.get('type_infos', {})
                    has_variant = type_infos.get('has_variant', False)
                    has_batch = type_infos.get('has_batch', False)
                    has_serialno = type_infos.get('has_serialno', False)
                    category_infos=prod_db.get('category_infos',{})
                    unit_infos=prod_db.get("unit_infos",{})
                    gst = prod_db.get('gst', '0%')

                    category_infos=prod_db.get('category_infos') or {}
                    unit_infos=prod_db.get('unit_infos') or {}

                    incoming_item_matches = validated_payload_map.get(product_id) or []
                    
                    for itm in incoming_item_matches:
                        variant_id = itm.get('variant_id')
                        batch_infos_payload = itm.get('batch_infos') or {}
                        inc_decr_type=itm['type']
                        # Match batch by ID directly from itm or payload fallback
                        batch_id = itm.get('batch_id') or batch_infos_payload.get('id')
                        batch_target_name = batch_infos_payload.get('name')
                        payload_serialno_infos = itm.get('serialno_infos') or []

                        variant_name = ''
                        batch_infos = {}
                        serialno_infos = []
                        stock_infos = {}
                        stl_infos = {}
                        rop_infos = {}
                        pricing_infos = {}

                        # --- Dynamic Scope Resolution Resolution Tree ---
                        if has_variant:
                            variants_dict = prod_db.get('variants', {})
                            variant_data = variants_dict.get(variant_id) if variants_dict else None
                            
                            if variant_data:
                                variant_name = variant_data.get('name', '')
                                
                                if has_batch:
                                    batches_list = variant_data.get('batch_infos', [])
                                    for b in batches_list:
                                        if (batch_id and b.get('id') == batch_id) or (batch_target_name and b.get('name') == batch_target_name):
                                            batch_infos = b
                                            break
                                    
                                    stock_infos = batch_infos.get('stock_infos') or {}
                                    serialno_infos = batch_infos.get('serialno_infos') or [] if has_serialno else []
                                    stl_infos = batch_infos.get("storage_location_infos") or {}
                                    rop_infos = batch_infos.get("reorder_point_infos") or {}
                                    pricing_infos = batch_infos.get('pricing_infos') or {}
                                else:
                                    stock_infos = variant_data.get('stock_infos') or {}
                                    serialno_infos = variant_data.get('serialno_infos') or [] if has_serialno else []
                                    stl_infos = variant_data.get("storage_location_infos") or {}
                                    rop_infos = variant_data.get("reorder_point_infos") or {}
                                    pricing_infos = variant_data.get('pricing_infos') or {}
                        else:
                            if has_batch:
                                batches_list = prod_db.get('batch_infos', [])
                                for b in batches_list:
                                    if (batch_id and b.get('id') == batch_id) or (batch_target_name and b.get('name') == batch_target_name):
                                        batch_infos = b
                                        break
                                
                                stock_infos = batch_infos.get('stock_infos') or {}
                                serialno_infos = batch_infos.get('serialno_infos') or [] if has_serialno else []
                                stl_infos = batch_infos.get("storage_location_infos") or {}
                                rop_infos = batch_infos.get("reorder_point_infos") or {}
                                pricing_infos = batch_infos.get('pricing_infos') or {}
                            else:
                                stock_infos = prod_db.get('stock_infos') or {}
                                serialno_infos = prod_db.get('serialno_infos') or [] if has_serialno else []
                                stl_infos = prod_db.get("storage_location_infos") or {}
                                rop_infos = prod_db.get("reorder_point_infos") or {}
                                pricing_infos = prod_db.get('pricing_infos') or {}

                        # Compute Safe Inventory Delta Strategy metrics
                        stocks = float(itm.get('qty', 0))
                        current_db_physical = float(stock_infos.get('physical_stocks', 0))
                        
                        if inc_decr_type=="INCREMENT":
                            stock_before = current_db_physical - stocks
                            if stock_before<0:
                                stock_before=0
                            ic(stock_before, current_db_physical, stocks)
                            stock_after = current_db_physical
                        elif inc_decr_type=="DECREMENT":
                            stock_before = current_db_physical + stocks
                            ic(stock_before, current_db_physical, stocks)
                            stock_after = current_db_physical

                        # Update transaction metadata
                        item_infos['total_adjustment_items'] += 1
                        
                        if inc_decr_type=="INCREMENT":
                            item_infos['total_adjustment_increment_stocks'] += stocks
                        elif inc_decr_type=="DECREMENT":
                            item_infos['total_adjustment_decrement_stocks'] += stocks

                        stockmovadj_item_id = generate_uuid()  
                        stockmovadj_items_toadd.append(StockMovAdjItems(
                            id=stockmovadj_item_id,
                            stock_move_adj_id=stock_mov_adj_id,
                            product_id=product_id,
                            variant_id=variant_id,
                            batch_id=batch_id,
                            serial_numbers=payload_serialno_infos,
                            type=inc_decr_type,
                            stocks=stocks,
                            stocks_before=stock_before,
                            stocks_after=stock_after
                        ))

                        read_db_variant_infos=None
                        if variant_id:
                            read_db_variant_infos = VariantInfo(
                                variant_id=variant_id,
                                variant_name=variant_name or 'Unknown'
                            )

                        read_db_batch_infos=None
                        if batch_infos:
                            read_db_batch_infos = BatchInfo(
                                batch_id=batch_infos.get('id'),
                                batch_name=batch_infos.get('name'),
                                mfg_date=batch_infos.get('manufacturing_date'),
                                exp_date=batch_infos.get('expiry_date')
                            )

                        stockmovadj_read_items.append(
                            StockMovementProduct(
                                product_id=product_id,
                                ui_id=db_ui_id,
                                name=product_name,
                                category_infos=category_infos,
                                unit_infos=unit_infos,
                                variant_infos=read_db_variant_infos,
                                batch_infos=read_db_batch_infos,
                                stock_infos={
                                    'stocks':stocks,
                                    'stocks_before':stock_before,
                                    'stocks_after':stock_after
                                },
                                type=inc_decr_type,
                                serial_numbers=[s.get('name', s) if isinstance(s, dict) else s for s in payload_serialno_infos]
                            )
                        )

                adjjusted_date = date_val
                if isinstance(adjjusted_date, str):
                    adjjusted_date = datetime.datetime.strptime(adjjusted_date, "%Y-%m-%d").date()

                stock_mov_adj_model = StockMovementAdjustment(
                    id=stock_mov_adj_id,
                    ui_id=ui_id,
                    shop_id=shop_id,
                    type=adj_type,
                    description=description,
                    additional_infos={}
                )

                await repo.create_bulk_adjustment([stock_mov_adj_model])
                await repo.create_bulk_items(stockmovadj_items_toadd)
                await session.commit()

                # 2. Read DB Insert
                read_model = StockMovementReadModel(
                    stock_movement_id=stock_mov_adj_id,
                    ui_id=ui_id,
                    shop_id=shop_id,
                    movement_type=adj_type,
                    adjusted_date=adjjusted_date,
                    description=description,
                    item_infos=item_infos,
                    products=stockmovadj_read_items
                )
                await StockMovementReadDbRepo.add_updatereaddb(read_model)

            return {
                "success": True,
                "execution": {
                    "step": "SUCCESS",
                    "service": "PURCHASE"
                }
            }

        if current_step == "SUCCESS":
            ic("Successfully completed the purchase cycle context workflow.")
            return {
                "success": True,
                "execution": None
            }

        




        