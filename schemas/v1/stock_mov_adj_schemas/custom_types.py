from pydantic import BaseModel
from typing import Optional,List
from datetime import date


class StockMovAdjSerialnoInfosType(BaseModel):
    id:Optional[str]=None
    name:str

class StockMovAdjStocksInfosType(BaseModel):
    id:str
    stocks:float
