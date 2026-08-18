"""Failure-mode demo: version mismatch (README Section 4d/4e).

Every JSON-RPC request carries an `A2A-Version` header. The server checks
the major version on every call: a mismatch is a loud, explicit
`VersionNotSupportedError` — not a silent misread of a request it can't
actually understand. A newer *minor* version is still accepted, since only
the major version has to match.
"""

import asyncio

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_message_text, new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest
from a2a.utils.constants import VERSION_HEADER
from a2a.utils.errors import VersionNotSupportedError

AGENT_URL = 'http://localhost:9001'
QUERY = 'flights from SFO to JFK on 2026-09-01'


async def _try_send(agent_card, httpx_client: httpx.AsyncClient, label: str) -> None:
    config = ClientConfig(
        httpx_client=httpx_client, streaming=False, polling=False
    )
    client = ClientFactory(config).create(agent_card)
    message = new_text_message(QUERY, role=Role.ROLE_USER)
    request = SendMessageRequest(message=message)

    sent_version = httpx_client.headers.get(VERSION_HEADER)
    print(f'--- {label} (A2A-Version: {sent_version}) ---')
    try:
        async for response in client.send_message(request):
            if response.HasField('message'):
                print(get_message_text(response.message))
    except VersionNotSupportedError as exc:
        print(f'VersionNotSupportedError (explicit, not silent): {exc.message}')
    finally:
        await client.close()
    print()


async def main() -> None:
    async with httpx.AsyncClient() as card_client:
        resolver = A2ACardResolver(card_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

    # 1. Matching version -> succeeds normally.
    async with httpx.AsyncClient() as ok_client:
        await _try_send(
            agent_card, ok_client, 'Matching version (1.0, the current default)'
        )

    # 2. Same major, newer minor -> still compatible (only major is checked).
    async with httpx.AsyncClient(headers={VERSION_HEADER: '1.7'}) as minor_client:
        await _try_send(
            agent_card, minor_client, 'Newer minor version (1.7) — still compatible'
        )

    # 3. Different major version -> explicit VersionNotSupportedError.
    async with httpx.AsyncClient(headers={VERSION_HEADER: '2.0'}) as bad_client:
        await _try_send(
            agent_card, bad_client, 'Mismatched major version (2.0)'
        )


if __name__ == '__main__':
    asyncio.run(main())
