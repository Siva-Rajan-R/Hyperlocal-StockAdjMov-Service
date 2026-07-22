from ..main import STOCK_MOVEMENT_COLLECTION
from ..models.stock_movement_model import StockMovementReadModel
from icecream import ic
from schemas.v1.stock_mov_adj_schemas.request_schema import GetAllStockMovAdjSchemas,GetStockAdjByInventoryIdSchema,GetStockMovAdjByIdSchema,GetStockMovAdjByShopIdSchema,GetStockMovAdjByProductIdSchema
from typing import List,Optional,Dict

class StockMovementReadDbRepo:

    @staticmethod
    async def create_stock_movement(data: StockMovementReadModel):
        try:
            document = data.model_dump(mode="json")
            result = await STOCK_MOVEMENT_COLLECTION.insert_one(document)
            ic(result.inserted_id)
            return True
        except Exception as e:
            ic(f"Error saving to Read DB: {e}")
            return False

    @staticmethod
    async def add_updatereaddb(data: StockMovementReadModel):
        try:
            document = data.model_dump(mode="json")
            result = await STOCK_MOVEMENT_COLLECTION.update_one(
                {"stock_movement_id": data.stock_movement_id, "shop_id": data.shop_id},
                {"$set": document},
                upsert=True
            )
            ic(result.upserted_id or result.modified_count)
            return True
        except Exception as e:
            ic(f"Error saving to Read DB: {e}")
            return False
        
    
    @staticmethod
    async def get_all(
        data:GetAllStockMovAdjSchemas
    ) -> List[dict]:
        try:
            from datetime import datetime
            query = {}

            if getattr(data, 'query', None):
                query["$or"] = [
                    {"ui_id": {"$regex": data.query, "$options": "i"}},
                    {"stock_movement_id": {"$regex": data.query, "$options": "i"}},
                    {"movement_type": {"$regex": data.query, "$options": "i"}},
                    {"description": {"$regex": data.query, "$options": "i"}}
                ]
            if getattr(data, 'from_date', None):
                try:
                    from_dt = datetime.strptime(data.from_date, "%Y-%m-%d")
                    if "created_at" not in query: query["created_at"] = {}
                    query["created_at"]["$gte"] = from_dt
                except Exception:
                    pass
            if getattr(data, 'to_date', None):
                try:
                    to_date_str = data.to_date
                    if len(to_date_str) <= 10: to_date_str += ' 23:59:59'
                    to_dt = datetime.strptime(to_date_str, "%Y-%m-%d %H:%M:%S")
                    if "created_at" not in query: query["created_at"] = {}
                    query["created_at"]["$lte"] = to_dt
                except Exception:
                    pass

            cursor = STOCK_MOVEMENT_COLLECTION.find(
                query,
                {"_id": 0}
            ).sort("created_at", -1)

            return await cursor.to_list(length=None)

        except Exception as e:
            ic(f"Error in get_all: {e}")
            return []

    @staticmethod
    async def get_by_shop_id(
        data:GetStockMovAdjByShopIdSchema
    ) -> List[dict]:
        try:
            from datetime import datetime
            query = {
                "shop_id": data.shop_id
            }

            if getattr(data, 'query', None):
                query["$or"] = [
                    {"ui_id": {"$regex": data.query, "$options": "i"}},
                    {"stock_movement_id": {"$regex": data.query, "$options": "i"}},
                    {"movement_type": {"$regex": data.query, "$options": "i"}},
                    {"description": {"$regex": data.query, "$options": "i"}}
                ]
            if getattr(data, 'from_date', None):
                try:
                    from_dt = datetime.strptime(data.from_date, "%Y-%m-%d")
                    if "created_at" not in query: query["created_at"] = {}
                    query["created_at"]["$gte"] = from_dt
                except Exception:
                    pass
            if getattr(data, 'to_date', None):
                try:
                    to_date_str = data.to_date
                    if len(to_date_str) <= 10: to_date_str += ' 23:59:59'
                    to_dt = datetime.strptime(to_date_str, "%Y-%m-%d %H:%M:%S")
                    if "created_at" not in query: query["created_at"] = {}
                    query["created_at"]["$lte"] = to_dt
                except Exception:
                    pass

            cursor = STOCK_MOVEMENT_COLLECTION.find(
                query,
                {"_id": 0}
            ).sort("created_at", -1)

            return await cursor.to_list(length=None)

        except Exception as e:
            ic(f"Error in get_by_shop_id: {e}")
            return []

    @staticmethod
    async def get_by_id(
        data:GetStockMovAdjByIdSchema
    ) -> Optional[dict]:
        try:
            query = {
                "shop_id": data.shop_id,
                "stock_movement_id": data.id,
            }

            return await STOCK_MOVEMENT_COLLECTION.find_one(
                query,
                {"_id": 0}
            )

        except Exception as e:
            ic(f"Error in get_by_id: {e}")
            return None

    @staticmethod
    async def get_by_product_id(
        data: GetStockMovAdjByProductIdSchema
    ) -> List[dict]:
        try:
            query = {
                "shop_id": data.shop_id,
                "products.product_id": data.product_id
            }
            cursor = STOCK_MOVEMENT_COLLECTION.find(
                query,
                {"_id": 0}
            ).sort("created_at", -1).skip((data.offset - 1) * data.limit).limit(data.limit)
            return await cursor.to_list(length=None)
        except Exception as e:
            ic(f"Error in get_by_product_id: {e}")
            return []
