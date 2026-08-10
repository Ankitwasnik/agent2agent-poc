"""Standalone A2A server for the Itinerary Planning Agent (polling)."""

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

from agent2agent.itinerary_planning.agent_executor import (
    ItineraryPlanningAgentExecutor,
)

HOST = 'localhost'
PORT = 9002


def build_agent_card() -> AgentCard:
    url = f'http://{HOST}:{PORT}{DEFAULT_RPC_URL}'
    return AgentCard(
        name='Itinerary Planning Agent',
        description=(
            'Drafts a day-by-day trip itinerary using an LLM. Drafting takes '
            'a while, so the agent returns a Task immediately and the client '
            'polls for completion instead of blocking or holding a stream open.'
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
                id='plan-itinerary',
                name='Plan Itinerary',
                description='Draft a day-by-day itinerary for a destination, duration, and interests.',
                tags=['itinerary', 'travel', 'planning'],
                examples=[
                    'Plan a 3-day itinerary for Tokyo focused on food and temples'
                ],
            )
        ],
    )


def build_app() -> Starlette:
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=ItineraryPlanningAgentExecutor(),
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
