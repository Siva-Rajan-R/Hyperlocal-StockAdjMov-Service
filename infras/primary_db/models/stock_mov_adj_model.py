from ..main import BASE
from sqlalchemy import (
    Column, String, Float, Boolean, BigInteger,ARRAY,
    TIMESTAMP, func, ForeignKey, Identity
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB


class StockMovementAdjustment(BASE):
    __tablename__ = "stock_movement_adjustment"

    id = Column(String, primary_key=True)
    sequence_id = Column(BigInteger, Identity(always=True), nullable=False)

    ui_id = Column(String, nullable=False, index=True)
    shop_id = Column(String, nullable=False)

    type = Column(String, nullable=False)
    description=Column(String)
    additional_infos = Column(JSONB)

    created_at = Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    items = relationship(
        "StockMovAdjItems",
        back_populates="stock_mov_adj",
        cascade="all, delete-orphan"
    )


class StockMovAdjItems(BASE):
    __tablename__ = "stock_movement_adjustment_items"

    id = Column(String, primary_key=True)

    stock_move_adj_id = Column(
        String,
        ForeignKey("stock_movement_adjustment.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    product_id = Column(String, nullable=False)
    variant_id = Column(String)
    batch_id = Column(String)
    serial_numbers=Column(ARRAY(JSONB))

    type = Column(String, nullable=False)

    stocks = Column(Float, nullable=False)
    stocks_before = Column(Float, nullable=False)
    stocks_after=Column(Float, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    stock_mov_adj = relationship(
        "StockMovementAdjustment",
        back_populates="items"
    )