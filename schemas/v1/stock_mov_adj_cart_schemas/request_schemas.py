from pydantic import BaseModel
from typing import Optional,List



class CartSerialNoInfos(BaseModel):
    id:Optional[str]=None
    name:str

class CartReserveRequest(BaseModel):
    session_id: str
    shop_id: str
    product_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None
    serialno_infos:Optional[List[CartSerialNoInfos]]=None
    qty: float
    type: str

class CartCompleteRequest(BaseModel):
    session_id: str
    shop_id: str
    description: Optional[str] = None
    type: str

class CartCancelRequest(BaseModel):
    session_id: str

class CartRemoveRequest(BaseModel):
    session_id: str
    product_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None