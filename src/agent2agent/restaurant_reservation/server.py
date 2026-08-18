"""Standalone A2A server for the Restaurant Reservation Agent (multi-turn)."""

import logging

import uvicorn
from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)
from a2a.utils.constants import DEFAULT_RPC_URL, TransportProtocol

from agent2agent.restaurant_reservation.agent_executor import (
    RestaurantReservationAgentExecutor,
)

HOST = 'localhost'
PORT = 9005


def build_agent_card() -> AgentCard:
    url = f'http://{HOST}:{PORT}{DEFAULT_RPC_URL}'
    return AgentCard(
        name='Restaurant Reservation Agent',
        description=(
            'Books a restaurant reservation across as many turns as it '
            'takes. If details are missing, the task pauses in an '
            'input-required state and asks — send a follow-up message '
            'with the same task ID to continue the same conversation.'
        ),
        version='0.1.0',
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding=TransportProtocol.JSONRPC,
                protocol_version='1.0',
            )
        ],
        capabilities=AgentCapabilities(
            streaming=False, push_notifications=False
        ),
        default_input_modes=['text/plain'],
        default_output_modes=['text/plain'],
        skills=[
            AgentSkill(
                id='book-reservation',
                name='Book Restaurant Reservation',
                description=(
                    'Book a table, asking follow-up questions across '
                    'multiple turns until every detail is confirmed.'
                ),
                tags=['reservation', 'dining', 'multi-turn'],
                examples=[
                    "I'd like to book a table at Le Jardin for tomorrow evening"
                ],
            )
        ],
    )


def build_app() -> Starlette:
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=RestaurantReservationAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = create_agent_card_routes(agent_card) + create_jsonrpc_routes(
        request_handler, rpc_url=DEFAULT_RPC_URL
    )
    return Starlette(routes=routes)


app = build_app()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=HOST, port=PORT)
