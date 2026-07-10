from infras.primary_db.services.stock_mov_adj_service import StockMovAdjService
from typing import Optional,List
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict,ErrorResponseTypDict,BaseResponseTypDict
from icecream import ic
from fastapi.exceptions import HTTPException
from core.utils.validate_fields import convert_field_type,validate_fields
from schemas.v1.stock_mov_adj_schemas.request_schema import CreateStockMovAdjSchema,GetAllStockMovAdjSchemas,GetStockMovAdjByIdSchema,GetStockMovAdjByShopIdSchema,DeleteStockMovAdjSchema,GetStockMovAdjByProductIdSchema
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum,SagaStateExecutionTypDict
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.utils.routingkey_builder import generate_routingkey,RoutingkeyState,RoutingkeyActions,RoutingkeyVersions
from infras.read_db.repos.stock_movement_repo import StockMovementReadDbRepo


class HandleStockMovAdjRequest:
    def __init__(self,session:AsyncSession):
        self.session=session
        self.stock_mov_adj_service_obj=StockMovAdjService(session=session)

    async def create(self,data:CreateStockMovAdjSchema):
        # Need to redfien based on the stock move adj datas 

        # validated_data = {}
        # product_serial_numbers = {}

        # for item in data.items:
        #     product_id = item.product_id
            
        #     if product_id not in validated_data:
        #         validated_data[product_id] = []
        #     else:
        #         validated_data_info = validated_data[product_id]
        #         inc_variant_id = item.variant_id
        #         inc_batch_id = item.batch_id

        #         for inside_data in validated_data_info:
        #             v_variant_id = inside_data.variant_id
        #             v_batch_id = inside_data.batch_id

        #             if v_variant_id == inc_variant_id and v_batch_id == inc_batch_id:
        #                 raise HTTPException(
        #                     status_code=400,
        #                     detail=ErrorResponseTypDict(
        #                         msg="Error : Creating Stock Movement Adjustment",
        #                         status_code=400,
        #                         description=f"Duplicate product with same variant or batch id could not be added",
        #                         success=False
        #                     )
        #                 )
            
        #     validated_data[product_id].append(item)

        #     if product_id not in product_serial_numbers:
        #         product_serial_numbers[product_id] = set()

        #     inc_serialnos = []
        #     if item.serialno_infos:
        #         for sn_info in item.serialno_infos:
        #             if sn_info.name:
        #                 inc_serialnos.append(sn_info.name)
        #     if item.serialno_infos:
        #         inc_serialnos.extend(item.serialno_infos)

        #     for sn in inc_serialnos:
        #         if sn in product_serial_numbers[product_id]:
        #             raise HTTPException(
        #                 status_code=400,
        #                 detail=ErrorResponseTypDict(
        #                     msg="Error : Creating Stock Movement Adjustment",
        #                     status_code=400,
        #                     description=f"Duplicate serial number '{sn}' for the same product could not be added",
        #                     success=False
        #                 )
        #             )
        #         product_serial_numbers[product_id].add(sn)
        
        res=await self.stock_mov_adj_service_obj.create_adjustment(data=data)
        ic(res)

        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                msg="Stock Movement Adjustment Creation Request Accepted",
                status_code=202,
                success=True
            )
        )
    
    

    async def delete(self,data:DeleteStockMovAdjSchema):
        res=await self.stock_mov_adj_service_obj.delete_adjustment(data=data)

        if res:
            return SuccessResponseTypDict(
                detail=BaseResponseTypDict(
                    msg="Stock Movement Adjustment deleted successfully",
                    status_code=200,
                    success=True
                )
            )
        
        raise HTTPException(
            status_code=400,
            detail=ErrorResponseTypDict(
                msg="Error : Deleting Stock Movement Adjustment",
                status_code=400,
                description=f"Invalid data types",
                success=False
            )
        )
    

    async def get_stock_movements(self,data:GetAllStockMovAdjSchemas):
        # res=await self.stock_mov_adj_service_obj.get_movements(data=data)
        res=await StockMovementReadDbRepo.get_all(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Stock Movements fetched successfully"
            ),
            data=res
        )
    
    async def get_stock_movements_by_shop_id(self,data:GetStockMovAdjByShopIdSchema):
        # res=await self.stock_mov_adj_service_obj.get_movements_by_shop_id(data=data)
        res=await StockMovementReadDbRepo.get_by_shop_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Stock Movements fetched successfully"
            ),
            data=res
        )
    

    async def get_stock_movements_by_id(self,data:GetStockMovAdjByIdSchema):
        # res=await self.stock_mov_adj_service_obj.get_movement_by_id(data=data)
        res=await StockMovementReadDbRepo.get_by_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Stock Movements fetched successfully"
            ),
            data=res
        )

    async def get_stock_movements_by_product_id(self,data:GetStockMovAdjByProductIdSchema):
        res=await StockMovementReadDbRepo.get_by_product_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Stock Movements fetched successfully"
            ),
            data=res
        )
        
