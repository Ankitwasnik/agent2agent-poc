"""Client for the Auth Demo Agent — demonstrates authentication + authorization.

Four calls, each as a different caller: no API key, a wrong API key, then
two valid, distinct users (Alice and Bob). The client never manually sets
an auth header — `AuthInterceptor` reads the fetched card's declared
`apiKeyAuth` scheme and asks a `CredentialService` for a credential, then
attaches it correctly on its own.
"""

import asyncio

import httpx

from a2a.client import (
    A2ACardResolver,
    AuthInterceptor,
    ClientCallContext,
    ClientConfig,
    ClientFactory,
    InMemoryContextCredentialStore,
)
from a2a.helpers.proto_helpers import get_artifact_text, new_text_message
from a2a.types.a2a_pb2 import AgentCard, ListTasksRequest, Role, SendMessageRequest

AGENT_URL = 'http://localhost:9102'
SCHEME_NAME = 'apiKeyAuth'

ALICE_API_KEY = 'alice-key-123'
BOB_API_KEY = 'bob-key-456'
WRONG_API_KEY = 'wrong-key-999'


async def _call_as(agent_card: AgentCard, api_key: str | None, label: str) -> None:
    """Sends a message and lists tasks as a given (or anonymous) caller."""
    print(f'--- {label} ---')

    async with httpx.AsyncClient() as httpx_client:
        credential_service = InMemoryContextCredentialStore()
        session_id = label
        if api_key:
            await credential_service.set_credentials(
                session_id, SCHEME_NAME, api_key
            )

        config = ClientConfig(
            httpx_client=httpx_client, streaming=False, polling=False
        )
        client = ClientFactory(config).create(
            agent_card, interceptors=[AuthInterceptor(credential_service)]
        )
        call_context = ClientCallContext(state={'sessionId': session_id})

        message = new_text_message('hello', role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        try:
            async for response in client.send_message(
                request, context=call_context
            ):
                if response.HasField('task'):
                    for artifact in response.task.artifacts:
                        print(f'  send_message -> {get_artifact_text(artifact)}')
        except Exception as exc:
            print(f'  send_message REJECTED: {exc}')
            await client.close()
            print()
            return

        tasks = await client.list_tasks(
            ListTasksRequest(), context=call_context
        )
        print(
            f'  tasks/list  -> {len(tasks.tasks)} task(s) visible to this caller'
        )

        await client.close()
    print()


async def main() -> None:
    async with httpx.AsyncClient() as card_client:
        resolver = A2ACardResolver(card_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

    print(
        f'Agent requires: {list(agent_card.security_schemes)} '
        '(fetched anonymously — the card itself needs no key)\n'
    )

    await _call_as(agent_card, None, 'Anonymous (no API key)')
    await _call_as(agent_card, WRONG_API_KEY, 'Invalid API key')
    await _call_as(agent_card, ALICE_API_KEY, 'Alice (valid key)')
    await _call_as(agent_card, BOB_API_KEY, 'Bob (valid key)')


if __name__ == '__main__':
    asyncio.run(main())
