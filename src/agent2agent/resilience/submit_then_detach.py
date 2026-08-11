"""Failure-mode demo, part 1 of 2 (README Section 4e): submit and walk away.

Submits an itinerary-planning task, prints its ID, and exits immediately —
no polling, no waiting, no held-open anything. The task keeps running on
the server, entirely independent of this process. Run `check_later.py
<task_id>` afterwards, from a completely separate process (and ideally
after a real gap — a few seconds, a minute, whatever), to prove the task's
state was never tied to this session in the first place.
"""

import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState

AGENT_URL = 'http://localhost:9002'
DEFAULT_QUERY = 'Plan a 3-day itinerary for Tokyo focused on food and temples'

_STATE_NAMES = {
    TaskState.TASK_STATE_SUBMITTED: 'SUBMITTED',
    TaskState.TASK_STATE_WORKING: 'WORKING',
}


async def main() -> None:
    query = ' '.join(sys.argv[1:]) or DEFAULT_QUERY

    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(
            httpx_client=httpx_client, streaming=False, polling=True
        )
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(query, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {query}')

        task = None
        async for response in client.send_message(request):
            if response.HasField('task'):
                task = response.task

        await client.close()

    if task is None:
        print('Agent did not return a task.')
        return

    print(f'Task submitted: {task.id}')
    print(f'Status: {_STATE_NAMES.get(task.status.state, task.status.state)}')
    print(
        '\nThis process is exiting now. The task keeps running on the '
        'server without it.\n'
        'In a separate terminal, whenever you like, run:\n\n'
        f'  uv run python -m agent2agent.resilience.check_later {task.id}'
    )


if __name__ == '__main__':
    asyncio.run(main())
