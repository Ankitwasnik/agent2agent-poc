"""Failure-mode demo, part 2 of 2 (README Section 4e): reattach after a real gap.

A completely separate process from `submit_then_detach.py` — new
interpreter, new httpx client, no shared memory of any kind. It only knows
the task_id it was given. Fetches the task fresh via `tasks/get` and, if
it's not done yet, polls until it is: proof the task's state lived on the
server the whole time, independent of any one client session.
"""

import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_artifact_text, get_message_text
from a2a.types.a2a_pb2 import GetTaskRequest, TaskState

AGENT_URL = 'http://localhost:9002'
POLL_INTERVAL_SECONDS = 2

_TERMINAL_STATES = {
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_REJECTED,
}

_STATE_NAMES = {
    TaskState.TASK_STATE_SUBMITTED: 'SUBMITTED',
    TaskState.TASK_STATE_WORKING: 'WORKING',
    TaskState.TASK_STATE_COMPLETED: 'COMPLETED',
    TaskState.TASK_STATE_FAILED: 'FAILED',
    TaskState.TASK_STATE_CANCELED: 'CANCELED',
    TaskState.TASK_STATE_REJECTED: 'REJECTED',
}


async def main() -> None:
    if len(sys.argv) < 2:
        print(
            'Usage: uv run python -m agent2agent.resilience.check_later <task_id>\n'
            'Get a task_id by running submit_then_detach.py first.'
        )
        return

    task_id = sys.argv[1]

    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(httpx_client=httpx_client, streaming=False)
        client = ClientFactory(config).create(agent_card)

        print(f'Reattaching to task {task_id} from a brand-new session...\n')
        task = await client.get_task(GetTaskRequest(id=task_id))
        print(f'Current status: {_STATE_NAMES[task.status.state]}')

        while task.status.state not in _TERMINAL_STATES:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            task = await client.get_task(GetTaskRequest(id=task_id))
            print(f'  poll: status: {_STATE_NAMES[task.status.state]}')

        print()
        if task.artifacts:
            for artifact in task.artifacts:
                print(get_artifact_text(artifact))
        elif task.status.HasField('message'):
            print(get_message_text(task.status.message))

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
