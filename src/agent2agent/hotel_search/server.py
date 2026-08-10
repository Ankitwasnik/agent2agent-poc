"""Standalone A2A server for the Hotel Search Agent (SSE streaming)."""

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

from agent2agent.hotel_search.agent_executor import HotelSearchAgentExecutor

HOST = 'localhost'
PORT = 9003


def build_agent_card() -> AgentCard:
    url = f'http://{HOST}:{PORT}{DEFAULT_RPC_URL}'
    return AgentCard(
        name='Hotel Search Agent',
        description=(
            'Searches for hotel options one at a time for a destination and '
            'date range, streaming each result live over SSE as it is found '
            'rather than returning everything at once.'
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
            streaming=True, push_notifications=False
        ),
        default_input_modes=['text/plain'],
        default_output_modes=['text/plain'],
        skills=[
            AgentSkill(
                id='search-hotels',
                name='Search Hotels',
                description=(
                    'Search for hotel options for a destination and date '
                    'range, streaming each result as it is found.'
                ),
                tags=['hotels', 'travel'],
                examples=[
                    'Find hotels in Tokyo for 2 guests, checking in 2026-09-10 and checking out 2026-09-14'
                ],
            )
        ],
    )


def build_app() -> Starlette:
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=HotelSearchAgentExecutor(),
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
