from pydantic import BaseModel
from typing import Optional,List
from datetime import date,datetime
from core.data_formats.enums.stock_mov_adj_enums import StockMovAdjItemTypeEnums,StockMovAdjTypeEnums
from .custom_types import StockMovAdjSerialnoInfosType,StockMovAdjStocksInfosType




# StockMovAdj ITMES
class CreateStockMovAdjItemsSchema(BaseModel):
    product_id:str
    variant_id:Optional[str]=None
    batch_id:Optional[str]=None
    serialno_infos:Optional[List[StockMovAdjSerialnoInfosType]]=None
    type:StockMovAdjItemTypeEnums
    stock_infos:StockMovAdjStocksInfosType



# StockMovAdj
class CreateStockMovAdjSchema(BaseModel):
    shop_id:str
    type:StockMovAdjTypeEnums
    description:Optional[str]=None
    session_id:str
    date:date




class DeleteStockMovAdjSchema(BaseModel):
    id:str
    shop_id:str



class GetAllStockMovAdjSchemas(BaseModel):
    limit:int=10
    offset:int=1
    q:Optional[str]=None

class GetStockMovAdjByShopIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    q:Optional[str]=None
    shop_id:str


class GetStockMovAdjByIdSchema(BaseModel):
    id:str
    shop_id:str

class GetStockAdjByInventoryIdSchema(BaseModel):
    shop_id: str
    inventory_id: str

class GetStockMovAdjByProductIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    shop_id:str
    product_id:str

from datetime import datetime

class EventCreateStockMovAdjItemSchema(BaseModel):
    product_id: str
    name: str
    ui_id: str
    category_id:str
    category_name:str
    unit_id:str
    unit_name:str
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    batch_id: Optional[str] = None
    batch_name: Optional[str] = None
    mfg_date: Optional[datetime] = None
    exp_date: Optional[datetime] = None
    serial_numbers: Optional[List[str]] = None
    type: StockMovAdjItemTypeEnums
    stocks_before: float
    stocks: float
    stocks_after: float

class EventCreateStockMovAdjSchema(BaseModel):
    shop_id: str
    type: StockMovAdjTypeEnums
    date: Optional[datetime] = None
    description: Optional[str] = None
    items: List[EventCreateStockMovAdjItemSchema]