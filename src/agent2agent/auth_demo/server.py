"""Standalone A2A server for the Auth Demo Agent (README Section 10).

Requires a per-user API key. Demonstrates two things at once:

  1. Authentication — the card declares `apiKeyAuth` as required, but that
     declaration does nothing on its own. Enforcement is `ApiKeyAuthBackend`
     below, an entirely ordinary Starlette `AuthenticationBackend` bolted on
     as middleware — nothing A2A-specific about it at all. The one
     deliberate exception: the agent-card route itself stays open to
     anonymous requests, because "fetch the card first, decide how to talk
     to the agent" only works if fetching it doesn't itself require
     credentials.

  2. Authorization — once a request carries a real authenticated user (not
     `UnauthenticatedUser`), `InMemoryTaskStore`'s owner-scoping isolates
     tasks per user with zero extra code here.
"""

import logging

import uvicorn
from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

from a2a.helpers.proto_helpers import new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    APIKeySecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    DEFAULT_RPC_URL,
    TransportProtocol,
)

HOST = 'localhost'
PORT = 9102
API_KEY_HEADER = 'X-API-Key'
SCHEME_NAME = 'apiKeyAuth'

# Stand-in for a real identity provider / credential store.
VALID_API_KEYS = {
    'alice-key-123': 'alice',
    'bob-key-456': 'bob',
}


class ApiKeyAuthBackend(AuthenticationBackend):
    """A completely ordinary Starlette auth backend — nothing A2A-specific.

    This is the missing piece Section 10 called out: A2A adapts to
    whatever ASGI auth middleware you install; it doesn't ship one itself.
    """

    async def authenticate(self, conn: HTTPConnection):
        if conn.url.path == AGENT_CARD_WELL_KNOWN_PATH:
            return None

        api_key = conn.headers.get(API_KEY_HEADER)
        if not api_key:
            raise AuthenticationError('Missing API key')

        user_name = VALID_API_KEYS.get(api_key)
        if not user_name:
            raise AuthenticationError(f'Invalid API key: {api_key!r}')

        return AuthCredentials(['authenticated']), SimpleUser(user_name)


def _on_auth_error(conn: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse({'error': str(exc)}, status_code=401)


def build_agent_card() -> AgentCard:
    url = f'http://{HOST}:{PORT}{DEFAULT_RPC_URL}'
    return AgentCard(
        name='Auth Demo Agent',
        description=(
            'Requires a per-user API key. Demonstrates authentication '
            '(rejects missing/invalid keys) and authorization (per-user '
            'task isolation).'
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
        security_schemes={
            SCHEME_NAME: SecurityScheme(
                api_key_security_scheme=APIKeySecurityScheme(
                    name=API_KEY_HEADER,
                    location='header',
                    description='A per-user API key.',
                )
            )
        },
        security_requirements=[
            SecurityRequirement(schemes={SCHEME_NAME: StringList(list=[])})
        ],
        skills=[
            AgentSkill(
                id='authenticated-echo',
                name='Authenticated Echo',
                description="Creates a task tagged with the caller's authenticated identity.",
                tags=['auth', 'demo'],
                examples=['hello'],
            )
        ],
    )


class AuthDemoExecutor(AgentExecutor):
    """Tags every task with whoever the server thinks authenticated it."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        user_name = context.call_context.user.user_name or '(anonymous)'
        text = context.get_user_input()

        await updater.add_artifact(
            [new_text_part(f"Hello, {user_name}! You said: {text!r}")],
            name='greeting',
        )
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        pass


def build_app() -> Starlette:
    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=AuthDemoExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = create_agent_card_routes(agent_card) + create_jsonrpc_routes(
        request_handler, rpc_url=DEFAULT_RPC_URL
    )
    middleware = [
        Middleware(
            AuthenticationMiddleware,
            backend=ApiKeyAuthBackend(),
            on_error=_on_auth_error,
        )
    ]
    return Starlette(routes=routes, middleware=middleware)


app = build_app()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=HOST, port=PORT)
