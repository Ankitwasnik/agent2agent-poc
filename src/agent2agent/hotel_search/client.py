"""Client for the Hotel Search Agent — demonstrates SSE streaming.

Sends one message and keeps the connection open, printing each event
(status update, incremental artifact chunk) as the agent streams it live —
no polling loop, no webhook, just one continuous SSE stream from request to
completion.
"""

import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_artifact_text, get_message_text, new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState

AGENT_URL = 'http://localhost:9003'
DEFAULT_QUERY = (
    'Find hotels in Tokyo for 2 guests, checking in 2026-09-10 and '
    'checking out 2026-09-14'
)

_STATE_NAMES = {
    TaskState.TASK_STATE_SUBMITTED: 'SUBMITTED',
    TaskState.TASK_STATE_WORKING: 'WORKING',
    TaskState.TASK_STATE_COMPLETED: 'COMPLETED',
    TaskState.TASK_STATE_FAILED: 'FAILED',
    TaskState.TASK_STATE_CANCELED: 'CANCELED',
    TaskState.TASK_STATE_REJECTED: 'REJECTED',
    TaskState.TASK_STATE_INPUT_REQUIRED: 'INPUT_REQUIRED',
    TaskState.TASK_STATE_AUTH_REQUIRED: 'AUTH_REQUIRED',
}


async def main() -> None:
    query = ' '.join(sys.argv[1:]) or DEFAULT_QUERY

    # No read timeout: the whole point is holding one connection open across
    # several provider checks, which take longer than httpx's default.
    async with httpx.AsyncClient(timeout=None) as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(httpx_client=httpx_client, streaming=True)
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(query, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {query}')
        print('Opening SSE stream...\n')

        async for response in client.send_message(request):
            if response.HasField('task'):
                task = response.task
                print(f'[task]     {task.id} — status: {_STATE_NAMES[task.status.state]}')
            elif response.HasField('status_update'):
                status = response.status_update.status
                state_name = _STATE_NAMES[status.state]
                text = (
                    get_message_text(status.message)
                    if status.HasField('message')
                    else ''
                )
                print(f'[status]   {state_name}' + (f': {text}' if text else ''))
            elif response.HasField('artifact_update'):
                text = get_artifact_text(response.artifact_update.artifact)
                print(f'[artifact] {text}')
            elif response.HasField('message'):
                print(get_message_text(response.message))

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
