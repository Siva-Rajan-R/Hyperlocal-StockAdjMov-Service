from pydantic import BaseModel
from typing import Optional,List
from datetime import date
from core.data_formats.enums.stock_mov_adj_enums import StockMovAdjItemTypeEnums,StockMovAdjTypeEnums
from .custom_types import StockMovAdjSerialnoInfosType,StockMovAdjStocksInfosType




# StockMovAdj ITMES
class CreateStockMovAdjItemsDbSchema(BaseModel):
    id:str
    product_id:str
    variant_id:Optional[str]=None
    batch_id:Optional[str]=None
    serialno_infos:Optional[List[StockMovAdjSerialnoInfosType]]=None
    type:StockMovAdjItemTypeEnums
    stock_infos:StockMovAdjStocksInfosType




# StockMovAdj
class CreateStockMovAdjDbSchema(BaseModel):
    id:str
    shop_id:str
    type:StockMovAdjTypeEnums
    description:Optional[str]=None
    date:date




class DeleteStockMovAdjDbSchema(BaseModel):
    id:str
    shop_id:str