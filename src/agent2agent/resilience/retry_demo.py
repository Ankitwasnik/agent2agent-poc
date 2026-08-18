"""Failure-mode demo: network flake (README Section 4d).

For a plain network flake, A2A gives you nothing special — the table's own
entry for this row is a dash. Retry-with-backoff is entirely the client's
job. This demo wraps the httpx transport so the first two attempts fail
with a simulated connection error, and shows a manual retry loop recovering
without ever involving the agent or the protocol itself.
"""

import asyncio

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError
from a2a.helpers.proto_helpers import get_message_text, new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest

AGENT_URL = 'http://localhost:9001'
QUERY = 'flights from SFO to JFK on 2026-09-01'

FAIL_FIRST_N_ATTEMPTS = 2
MAX_ATTEMPTS = 4
BASE_DELAY_SECONDS = 0.5


class FlakyTransport(httpx.AsyncBaseTransport):
    """Wraps a real transport but fails the first N requests, simulating a flaky network."""

    def __init__(self, real_transport: httpx.AsyncBaseTransport, fail_first_n: int):
        self._real = real_transport
        self._fail_first_n = fail_first_n
        self._attempts = 0

    async def handle_async_request(
        self, request: httpx.Request
    ) -> httpx.Response:
        self._attempts += 1
        if self._attempts <= self._fail_first_n:
            raise httpx.ConnectError(
                f'simulated network flake (attempt {self._attempts})',
                request=request,
            )
        return await self._real.handle_async_request(request)

    async def aclose(self) -> None:
        await self._real.aclose()


async def send_with_retry(client, request: SendMessageRequest):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async for response in client.send_message(request):
                if response.HasField('message'):
                    return response.message
            return None
        except A2AClientError as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(
                f'Attempt {attempt} failed ({exc}) — retrying in {delay:.1f}s...'
            )
            await asyncio.sleep(delay)
    return None


async def main() -> None:
    # Card resolution uses a normal, non-flaky client — only the actual RPC
    # call below is subject to the simulated flake.
    async with httpx.AsyncClient() as card_client:
        resolver = A2ACardResolver(card_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

    flaky_client = httpx.AsyncClient(
        transport=FlakyTransport(
            httpx.AsyncHTTPTransport(), fail_first_n=FAIL_FIRST_N_ATTEMPTS
        )
    )
    async with flaky_client:
        config = ClientConfig(
            httpx_client=flaky_client, streaming=False, polling=False
        )
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(QUERY, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {QUERY}')
        print(
            f'Simulating a flaky connection: the first '
            f'{FAIL_FIRST_N_ATTEMPTS} attempt(s) will fail.\n'
        )

        result = await send_with_retry(client, request)
        if result is not None:
            print(f'\nSucceeded after retrying:\n{get_message_text(result)}')

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
