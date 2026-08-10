"""Client for the Flight Search Agent — demonstrates synchronous request/response.

Sends one message, blocks until the agent has fully processed it, and prints
the single Message it returns. No task ID, no polling loop, no stream to hold
open: the whole exchange is one call in, one call out.
"""

import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_message_text, new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest

AGENT_URL = 'http://localhost:9001'
DEFAULT_QUERY = 'need to get from the bay area to nyc sometime next month'


async def main() -> None:
    query = ' '.join(sys.argv[1:]) or DEFAULT_QUERY

    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(
            httpx_client=httpx_client, streaming=False, polling=False
        )
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(query, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {query}')
        print('Sending request, blocking until the agent responds...\n')

        async for response in client.send_message(request):
            if response.HasField('message'):
                print(get_message_text(response.message))
            elif response.HasField('task'):
                print(f'Unexpected task response: {response.task}')

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
