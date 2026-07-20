import httpx
from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated, Optional
from datetime import datetime, timezone, timedelta
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict, BaseResponseTypDict, ErrorResponseTypDict
from infras.caching.models.cart_model import StockAdjustmentCartCacheModel
from schemas.v1.stock_mov_adj_schemas.request_schema import EventCreateStockMovAdjSchema
from infras.primary_db.main import AsyncSession, get_pg_async_session
from pydantic import BaseModel
from schemas.v1.stock_mov_adj_cart_schemas.request_schemas import CartCancelRequest,CartCompleteRequest,CartRemoveRequest,CartReserveRequest
from icecream import ic


# BASE_URL="http://127.0.0.1:8004/inventories/inventories"
BASE_URL="http://inventory-service:8000/inventories/inventories"
TTL_MINUTES = 3

async def create_reservation(data:CartReserveRequest):
    cart = StockAdjustmentCartCacheModel(data.session_id)
    existing_cart = await cart.get_cart()
    ic(existing_cart)
    if existing_cart is None:
        raise HTTPException(status_code=400, detail="Invalid or expired session")
    
    exc_type=data.type
    for exc in existing_cart:
        if data.product_id == exc['product_id']:
            exc_type=exc['type']
    # Expires logic
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TTL_MINUTES)
    
    if exc_type=="DECREMENT" and data.type=="INCREMENT":
        res=await remove_reservation_item(data=CartRemoveRequest(
            session_id=data.session_id,
            product_id=data.product_id,
            variant_id=data.variant_id,
            batch_id=data.batch_id
        ))
        ic(res)
        if not res:
            raise HTTPException(status_code=500, detail=f"Failed to communicate with Inventory Service")
        
    # Only reserve inventory if we are reducing stock
    if data.type == "DECREMENT":
        payload = {
            "session_id": data.session_id,
            "product_id": data.product_id,
            "variant_id": data.variant_id,
            "batch_id": data.batch_id,
            "shop_id": data.shop_id,
            "qty": data.qty,
            "serialno_infos": [
                s.model_dump(mode="json") for s in data.serialno_infos
            ] if data.serialno_infos else [],
            "expires_at": expires_at.isoformat(),
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{BASE_URL}/reservations/reserve", json=payload)
                ic(response)
                ic(response.status_code)
                ic(response.url)
                ic(response.text)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise HTTPException(status_code=500, detail=f"Failed to communicate with Inventory Service: {e}")

    # Add to cart
    await cart.add_or_update_item(item=data.model_dump(), ttl=TTL_MINUTES * 60)

    return True




async def commit_reservation(session_id:str):
    cart = StockAdjustmentCartCacheModel(session_id)
    items = await cart.get_cart()
    
    if items is None or len(items) == 0:
        raise HTTPException(status_code=400, detail="Cart is empty or session expired")

    # 1. Commit reservations in inventory service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/reservations/commit", json={"session_id": session_id,"entity_name":"STOCKMOVADJ"})
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Failed to commit inventory reservations: {e}")

    # 3. Clean up Redis
    await cart.delete_cart()

    return True




async def remove_reservation_item(data:CartRemoveRequest):
    cart = StockAdjustmentCartCacheModel(data.session_id)
    
    # Release the specific reservation item
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "session_id": data.session_id,
                "product_id": data.product_id,
                "variant_id": data.variant_id,
                "batch_id": data.batch_id
            }
            await client.post(f"{BASE_URL}/reservations/release-item", json=payload)
        except httpx.HTTPError:
            pass # Graceful failure
            
    await cart.remove_item(
        product_id=data.product_id, 
        variant_id=data.variant_id, 
        batch_id=data.batch_id, 
        ttl=TTL_MINUTES * 60
    )

    return True



async def cancel_reservation(data:CartCancelRequest):
    cart = StockAdjustmentCartCacheModel(data.session_id)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/reservations/release", json={"session_id": data.session_id})
        except httpx.HTTPError as e:
            pass # Graceful failure
            
    await cart.delete_cart()

    return True