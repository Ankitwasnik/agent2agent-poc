"""Client for the Itinerary Planning Agent — demonstrates polling.

Sends one message, gets a Task back immediately (SUBMITTED), then polls
tasks/get on an interval until the task reaches a terminal state. No stream
held open, no webhook registered — just periodic check-ins.
"""

import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import (
    get_artifact_text,
    get_message_text,
    new_text_message,
)
from a2a.types.a2a_pb2 import GetTaskRequest, Role, SendMessageRequest, TaskState

AGENT_URL = 'http://localhost:9002'
DEFAULT_QUERY = 'Plan a 3-day itinerary for Tokyo focused on food and temples'
POLL_INTERVAL_SECONDS = 3

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
    TaskState.TASK_STATE_INPUT_REQUIRED: 'INPUT_REQUIRED',
    TaskState.TASK_STATE_AUTH_REQUIRED: 'AUTH_REQUIRED',
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
        print('Sending request...\n')

        task = None
        async for response in client.send_message(request):
            if response.HasField('task'):
                task = response.task

        if task is None:
            print('Agent did not return a task.')
            await client.close()
            return

        print(f'Task {task.id} submitted, status: {_STATE_NAMES[task.status.state]}')

        poll_count = 0
        while task.status.state not in _TERMINAL_STATES:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            poll_count += 1
            task = await client.get_task(GetTaskRequest(id=task.id))
            print(f'  poll #{poll_count}: status: {_STATE_NAMES[task.status.state]}')

        print()
        if task.artifacts:
            for artifact in task.artifacts:
                print(get_artifact_text(artifact))
        elif task.status.HasField('message'):
            print(get_message_text(task.status.message))
        else:
            print(f'Task ended with no artifact or message (state: {_STATE_NAMES[task.status.state]}).')

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
