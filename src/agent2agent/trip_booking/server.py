"""Standalone A2A server for the Trip Booking Agent (long-running + multi-turn)."""

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

from agent2agent.trip_booking.agent_executor import TripBookingAgentExecutor

HOST = 'localhost'
PORT = 9006


def build_agent_card() -> AgentCard:
    url = f'http://{HOST}:{PORT}{DEFAULT_RPC_URL}'
    return AgentCard(
        name='Trip Booking Agent',
        description=(
            'Books a flight + hotel for a trip. Searching genuinely takes '
            'a while (poll for progress), and midway the task pauses to '
            'ask which flight option you want — send a follow-up message '
            'with the same task ID to resume, and the remaining booking '
            'work continues from there.'
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
                id='book-trip',
                name='Book Trip',
                description=(
                    'Search flights and hotels for a trip, pausing '
                    'mid-task for a flight choice before finalizing.'
                ),
                tags=['booking', 'travel', 'multi-turn', 'long-running'],
                examples=['Book me a trip to Tokyo. My budget is $2000.'],
            )
        ],
    )


def build_app() -> Starlette:
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=TripBookingAgentExecutor(),
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
