from models.repo_models.base_repo_model import BaseRepoModel
from models.service_models.base_service_model import BaseServiceModel
from sqlalchemy import select,update,delete,func,or_,and_,String,case,literal,literal_column,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload,load_only
from ..repos.stock_mov_adj_repo import StockMovAdjRepo
from ..models.stock_mov_adj_model import StockMovAdjItems,StockMovementAdjustment
from schemas.v1.stock_mov_adj_schemas.db_schemas import CreateStockMovAdjDbSchema,CreateStockMovAdjItemsDbSchema,DeleteStockMovAdjDbSchema
from schemas.v1.stock_mov_adj_schemas.request_schema import GetAllStockMovAdjSchemas,GetStockMovAdjByIdSchema,GetStockMovAdjByShopIdSchema,CreateStockMovAdjItemsSchema,CreateStockMovAdjSchema,DeleteStockMovAdjSchema
from sqlalchemy.dialects.postgresql import insert
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from typing import Optional,List
from icecream import ic
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from core.data_formats.enums.stock_mov_adj_enums import StockMovAdjTypeEnums,StockMovAdjItemTypeEnums
from hyperlocal_platform.core.enums.saga_state_enum import SagaStatusEnum,SagaStepsValueEnum
from integrations.stocks_reservation import commit_reservation
from infras.caching.models.cart_model import StockAdjustmentCartCacheModel
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum,SagaStateExecutionTypDict



class StockMovAdjService:
    def __init__(self, session:AsyncSession):
        self.session=session
        self.stock_mov_adj_obj=StockMovAdjRepo(session=session)

    @start_db_transaction
    async def get_next_sequence(self, shop_id: str, start_from: int) -> int:
        from sqlalchemy import text
        seq_name = f"seq_purchase_{shop_id.replace('-', '_').lower()}"
        await self.session.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START WITH {start_from}"))
        res = await self.session.execute(text(f"SELECT nextval('{seq_name}')"))
        return res.scalar_one()

    @start_db_transaction
    async def create_adjustment(self,data:CreateStockMovAdjSchema):
        cart = StockAdjustmentCartCacheModel(data.session_id)
        items = await cart.get_cart()

        reservation_complete_res=await commit_reservation(session_id=data.session_id)
        if not reservation_complete_res:
            ic("Cant able to reserve the stocks please try again")
            return False

        await cart.delete_cart()
            

        saga_id:str=generate_uuid()

        body=[]
        product_ids=[]

        for item in items:
            ic(item)
            if item['type']=="INCREMENT":
                body.append(
                    {
                        "shop_id":data.shop_id,
                        "product_id":item['product_id'],
                        "variant_id":item['variant_id'],
                        "batch_infos":{"id":item['batch_id']},
                        "stocks":item['qty'],
                        "serialno_infos":item['serialno_infos'],
                        "type":"INCREMENT",
                        'entity_name': data.type.value if hasattr(data.type, 'value') else data.type
                    }
                )
            elif item['type']=="DECREMENT":
                product_ids.append(item['product_id'])

        stock_adj_datas={**data.model_dump(mode="json"),"items":items}

        saga_data={"stock_mov_adj":stock_adj_datas}
        
        if body:
            await SagaProducer.emit(
                saga_payload=CreateSagaStateSchema(
                    id=saga_id,
                    status=SagaStatusEnum.IN_PROGRESS,
                    type="STOCK_MOV_ADJ_CREATED",
                    steps={
                        "PRODUCT_VERIFY_UPDATE":SagaStepsValueEnum.PENDING,
                        "FETCHING_PRODUCTS":SagaStepsValueEnum.PENDING
                    },
                    execution=SagaStateExecutionTypDict(
                        step="PRODUCT_VERIFY_UPDATE",
                        service="PRODUCTS"
                    ),
                    data=saga_data
                ),
                routing_key="products.service.routing.key",
                exchange_name="products.service.exchange",
                headers={
                    "reply_key":"None",
                    "reply_exchange":"None",
                    "reply_entity_name":"None",
                    "reply_service_name":"STOCK_MOV_ADJ",
                    "service_name":"PRODUCTS",
                    "entity_name":"update_bulk_prodinv",
                    "body":body
                }
            )
            
        elif product_ids:
            await SagaProducer.emit(
                saga_payload=CreateSagaStateSchema(
                    id=saga_id,
                    status=SagaStatusEnum.IN_PROGRESS,
                    type="STOCK_MOV_ADJ_CREATED",
                    steps={
                        "FETCHING_PRODUCTS":SagaStepsValueEnum.PENDING
                    },
                    execution=SagaStateExecutionTypDict(
                        step="FETCHING_PRODUCTS",
                        service="PRODUCTS"
                    ),
                    data=saga_data
                ),
                routing_key="products.service.routing.key",
                exchange_name="products.service.exchange",
                headers={
                    "reply_key":"None",
                    "reply_exchange":"None",
                    "reply_entity_name":"None",
                    "reply_service_name":"STOCK_MOV_ADJ",
                    "service_name":"PRODUCTS",
                    "entity_name":"get_bulk_product_by_id",
                    "body":{
                        "shop_id":data.shop_id,
                        "id":list(set(product_ids))
                    }
                }
            )


        return True
    
    
    @start_db_transaction
    async def delete_adjustment(self,data:DeleteStockMovAdjSchema):
        final_data=DeleteStockMovAdjDbSchema(**data.model_dump(mode="json"))
        res=await self.stock_mov_adj_obj.delete_adjustment(data=data)
        if res:
            try:
                adj_name = f"Stock Adjustment #{data.id[:8]}"
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": data.shop_id,
                        "user_name": "Hyperlocal-User",
                        "service": "StockAdjustment",
                        "action": "DELETED",
                        "entity_type": "STOCK_ADJUSTMENT",
                        "entity_id": str(data.id),
                        "entity_name": str(adj_name),
                        "description": f"Deleted Stock Adjustment {adj_name} ({data.id})",
                        "changes": []
                    },
                    headers={}
                )
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")
        return res
    
    async def get_movements(self,data:GetAllStockMovAdjSchemas):
        res=await self.stock_mov_adj_obj.get_movements(data=data)
        return res
    
    async def get_movements_by_shop_id(self,data:GetStockMovAdjByShopIdSchema):
        res=await self.stock_mov_adj_obj.get_movements_by_shop_id(data=data)
        return res
    

    async def get_movement_by_id(self,data:GetStockMovAdjByIdSchema):
        res=await self.stock_mov_adj_obj.get_movement_by_id(data=data)
        ic(res)
        return res


    
    
