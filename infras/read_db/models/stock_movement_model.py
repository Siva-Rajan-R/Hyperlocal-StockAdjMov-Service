from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, Field


class SerialInfo(BaseModel):
    serialno_id: str
    serial_numbers: List[str] = []


class VariantInfo(BaseModel):
    variant_id: str
    variant_name: str


class BatchInfo(BaseModel):
    batch_id: str
    batch_name: str
    mfg_date: Optional[datetime] = None
    exp_date: Optional[datetime] = None


class StockMovementProduct(BaseModel):
    product_id: str
    ui_id: str
    name: str
    category_infos:dict={}
    unit_infos:dict={}

    stock_infos:dict={
        "stocks_before": 0.0,
        "stocks": 0.0,
        "stocks_after": 0.0
    }
    
    type: str # INCREMENT or DECREMENT

    variant_infos: Optional[VariantInfo] = None
    batch_infos: Optional[BatchInfo] = None
    serial_numbers: Optional[List[str]] = None



class StockMovementReadModel(BaseModel):
    stock_movement_id: str
    ui_id: str
    shop_id: str
    
    movement_type: str
    adjusted_date: datetime
    description: str
    
    item_infos:dict={}

    products: List[StockMovementProduct] = []

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StockMovementStatsReadModel(BaseModel):
    shop_id: str
    total_stock_in: float = 0.0
    total_stock_out: float = 0.0
    total_movements_count: int = 0
    
    total_purchase_count: int = 0
    total_sales_count: int = 0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
