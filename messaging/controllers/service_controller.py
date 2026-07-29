from aio_pika.abc import AbstractIncomingMessage
import orjson,inspect
from icecream import ic

from messaging.main import RabbitMQMessagingConfig
from models.messaging_models.consumer_model import BaseConsumerModel
from hyperlocal_platform.infras.saga.schemas import CreateSagaStateSchema,UpdateSagaStateSchema
from hyperlocal_platform.infras.saga.repo import SagaStatesRepo
from core.errors.messaging_errors import BussinessError,RetryableError,FatalError
from hyperlocal_platform.core.enums.saga_state_enum import SagaStatusEnum,SagaStepsValueEnum
from hyperlocal_platform.core.enums.routingkey_enum import RoutingkeyState,RoutingkeyActions
from hyperlocal_platform.infras.saga.schemas import SagaStateExecutionTypDict,SagaStateErrorTypDict
from hyperlocal_platform.infras.saga.main import AsyncInfraDbLocalSession
from hyperlocal_platform.core.typed_dicts.messaging_typdict import SuccessMessagingTypDict,EventPublishingTypDict
from core.utils.exception_serializer import serialize_exception
from hyperlocal_platform.core.typed_dicts.messaging_typdict import EventPublishingTypDict
from hyperlocal_platform.core.utils.routingkey_builder import generate_routingkey
from typing import Optional
from hyperlocal_platform.core.basemodels.readdb_model import ReadDbBaseModel
from core.constants import SERVICE_NAME
from ..msgqueue_services.stock_mov_adj_msgqueue_service import MessagingQueueStockMovAdjService


MESSAGING_QUEUE_SERVICE_MAPPER_BY_SERVICE_NAME={
    "STOCK_MOV_ADJ": MessagingQueueStockMovAdjService
}

SERVICE_NAME='STOCK_MOV_ADJ'



async def service_main_controller(msg:AbstractIncomingMessage):
    async with AsyncInfraDbLocalSession() as session:
        payload=orjson.loads(msg.body)
        headers:dict=msg.headers
        saga_id:str=headers.get("saga_id")

        reply_key:str=headers.get("reply_key")
        reply_exchange:str=headers.get("reply_exchange")
        reply_entity_name:str=headers.get("reply_entity_name")
        entity_name:str=headers.get("entity_name")
        service_name:str=headers.get("service_name")
        body:dict=headers.get("body")

        saga_repo=SagaStatesRepo(session=session)
        ic(payload,headers,saga_id,reply_entity_name,reply_key,reply_exchange,entity_name,service_name,body)
        try:
            
            # Check for domain event without saga
            is_domain_event = not saga_id and not reply_key
            
            if not is_domain_event and (not entity_name or not body or not saga_id or not reply_key or not reply_exchange or not reply_entity_name or not service_name):
                ic("One or more required fields are missing in the message headers")
                await saga_repo.update_status(
                    status=SagaStatusEnum.CANCELED,
                    saga_id=saga_id
                )
                await saga_repo.update_error(
                    saga_id=saga_id,
                    error=SagaStateErrorTypDict(
                        code="BUSSINESS_ERROR",
                        debug=f"entity_name, body, saga_id, reply_key, reply_exchange, reply_entity_name and service_name are required in the message headers ({entity_name}, {body}, {saga_id}, {reply_key}, {reply_exchange}, {reply_entity_name}, {service_name})",
                        user_msg="One or more required fields are missing in the message headers"
                    )
                )
                
                await session.commit()
                return False

            service = MESSAGING_QUEUE_SERVICE_MAPPER_BY_SERVICE_NAME.get(service_name.upper())
            
            if not service:
                ic(f"Service name '{service_name}' is not recognized")
                if not is_domain_event:
                    await saga_repo.update_status(
                        status=SagaStatusEnum.CANCELED,
                        saga_id=saga_id
                    )
                    await saga_repo.update_error(
                        saga_id=saga_id,
                        error=SagaStateErrorTypDict(
                            code="BUSSINESS_ERROR",
                            debug=f"service_name '{service_name}' is not recognized",
                            user_msg="Service name in the message headers is not recognized, please check and try again"
                        )
                    )
                    await session.commit()
                return False

                return False
            method = getattr(service(), entity_name, None)
            ic("Method => ",method)
            ic(not method)
            if not method:
                ic(f"Entity name '{entity_name}' is not recognized")
                if not is_domain_event:
                    await saga_repo.update_status(
                        status=SagaStatusEnum.CANCELED,
                        saga_id=saga_id
                    )
                    await saga_repo.update_error(
                        saga_id=saga_id,
                        error=SagaStateErrorTypDict(
                            code="BUSSINESS_ERROR",
                            debug=f"entity_name '{entity_name}' is not recognized",
                            user_msg="Entity name in the message headers is not recognized, please check and try again"
                        )
                    )
                    await session.commit()
                return False

                return False
            

            if inspect.iscoroutinefunction(method):
                response = await method(data=body)
            else:
                response = method(data=body)
                
            ic(response)
            if response is not None:
                ic(f"Successfully processed the message for entity '{entity_name}' with response: {response}")
                if not is_domain_event:
                    await saga_repo.merge(
                        data=response,
                        saga_id=saga_id,
                        service=SERVICE_NAME.lower()
                    )

            else:
                ic(f"Failed to process the message for entity '{entity_name}'")
                if not is_domain_event and saga_id and saga_id != "none":
                    await saga_repo.update_status(
                        status=SagaStatusEnum.CANCELED,
                        saga_id=saga_id
                    )
                    await saga_repo.update_error(
                        saga_id=saga_id,
                        error=SagaStateErrorTypDict(
                            code="BUSSINESS_ERROR",
                            debug=f"Processing the message for entity '{entity_name}' failed without exceptions, {response}",
                            user_msg="Failed to process the message due to bussiness error, please check the data and try again"
                        )
                    )
                

            if not is_domain_event and session.in_transaction():
                await session.commit()


            return 


        except Exception as e:
            debug_msg=serialize_exception(e)
            ic(f"An error occurred while processing the message: {e}")
            if not is_domain_event and saga_id and saga_id != "none":
                await saga_repo.update_status(
                        status=SagaStatusEnum.CANCELED,
                        saga_id=saga_id
                    )
                await saga_repo.update_error(
                    saga_id=saga_id,
                    error=SagaStateErrorTypDict(
                        code="FATAL_ERROR",
                        debug=f"Processing the message for entity '{entity_name}' failed with exceptions, {debug_msg}",
                        user_msg="Failed to process the message due to fatal error, please check the data and try again"
                    )
                )
            if not is_domain_event and session.in_transaction():
                await session.commit()

            return False

            return False
        
        finally:
            ic("Finally publishing the event to reply exchange")
            ic(reply_exchange,reply_key)
            if reply_exchange!="None" and reply_key!="None":
                if reply_key and reply_exchange:
                    await RabbitMQMessagingConfig().publish_event(
                        routing_key=reply_key,
                        payload=payload,
                        headers=headers,
                        exchange_name=reply_exchange
                    )

            await msg.ack()

            return True

