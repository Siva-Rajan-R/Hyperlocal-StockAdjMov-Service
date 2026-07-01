from fastapi import FastAPI
from api.routers.v1 import stock_mov_adj_route
from api.routers.v1 import cart_routes
from contextlib import asynccontextmanager
from icecream import ic
from dotenv import load_dotenv
from core.configs.settings_config import SETTINGS
from infras.primary_db.main import init_inventory_pg_db
from hyperlocal_platform.core.enums.environment_enum import EnvironmentEnum
import os,asyncio
from hyperlocal_platform.infras.saga.main import init_infra_db
from messaging.worker import worker
from infras.caching.main import redis_client,check_redis_health
load_dotenv()


@asynccontextmanager
async def inventory_service_lifespan(app:FastAPI):
    try:
        ic("Starting Stock Mov-Adj service...")
        await init_infra_db()
        await init_inventory_pg_db()
        await check_redis_health()
        # await redis_client.flushdb()
        asyncio.create_task(worker())
        yield

    except Exception as e:
        ic(f"Error : Starting Stock Mov-Adj => {e}")

    finally:
        ic("...Stoping Stock Mov-Adj...")

debug=False
openapi_url=None
docs_url=None
redoc_url=None

if SETTINGS.ENVIRONMENT.value==EnvironmentEnum.DEVELOPMENT.value:
    debug=True
    openapi_url="/openapi.json"
    docs_url="/docs"
    redoc_url="/redoc"

app=FastAPI(
    title="Stock Mov-Adj",
    description="This service contains all the CRUD operations for Stock Mov-Adj service",
    debug=debug,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=inventory_service_lifespan,
    root_path="/inventories"

)



# Routes to include

app.include_router(stock_mov_adj_route.router)
app.include_router(cart_routes.router)



