"""Standalone A2A server for the Flight Search Agent (sync request/response)."""

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

from agent2agent.flight_search.agent_executor import FlightSearchAgentExecutor

HOST = 'localhost'
PORT = 9001


def build_agent_card() -> AgentCard:
    url = f'http://{HOST}:{PORT}{DEFAULT_RPC_URL}'
    return AgentCard(
        name='Flight Search Agent',
        description=(
            'Uses an LLM to parse free-form flight requests (fuzzy cities, '
            'relative dates) into a structured search, then looks up flights '
            'between the resolved airports. Synchronous only: one request in, '
            'one answer back.'
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
                id='search-flights',
                name='Search Flights',
                description='Search for flights between two airports on a given date, understanding free-form requests.',
                tags=['flights', 'travel'],
                examples=[
                    'flights from SFO to JFK on 2026-09-01',
                    'need to get from the bay area to nyc sometime next month',
                ],
            )
        ],
    )


def build_app() -> Starlette:
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=FlightSearchAgentExecutor(),
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
