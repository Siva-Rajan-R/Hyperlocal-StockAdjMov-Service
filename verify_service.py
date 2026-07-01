from dotenv import load_dotenv
load_dotenv()
from messaging.msgqueue_services.stock_mov_adj_msgqueue_service import MessagingQueueStockMovAdjService
from infras.primary_db.main import init_inventory_pg_db
from hyperlocal_platform.infras.saga.main import init_infra_db
import asyncio

async def test_service():
    await init_infra_db()
    await init_inventory_pg_db()
    
    service = MessagingQueueStockMovAdjService()
    
    payload = {
        "shop_id": "shop-123",
        "type": "ADJUSTMENT",
        "description": "test adjustment",
        "items": [
            {
                "product_id": "prod-123",
                "name": "Product 123",
                "ui_id": "PRD-123",
                "variant_id": None,
                "batch_id": None,
                "type": "INCREMENT",
                "stocks_before": 0.0,
                "stocks_adjusted": 5.0,
                "stocks_after": 5.0,
                "storage_location": "Default"
            }
        ]
    }
    
    try:
        res = await service.create_adjustment(payload)
        print("Success:", res)
    except Exception as e:
        print("Error during test:", e)

if __name__ == "__main__":
    asyncio.run(test_service())
