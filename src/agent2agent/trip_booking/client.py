"""Client for the Trip Booking Agent — long-running work with a mid-task pause.

Submits the trip request, polls while the agent searches for flights (real
WORKING time), answers the mid-task flight-choice question with a
follow-up message using the SAME task ID, then polls again while the agent
finalizes the booking (hotel + confirmation) — all without ever holding a
stream open.
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
from a2a.types.a2a_pb2 import (
    GetTaskRequest,
    Role,
    SendMessageRequest,
    Task,
    TaskState,
)

AGENT_URL = 'http://localhost:9006'
DEFAULT_OPENER = 'Book me a trip to Tokyo. My budget is $2000.'
FLIGHT_CHOICE_REPLY = "I'll take the cheaper one with the stopover."
POLL_INTERVAL_SECONDS = 2

_TERMINAL_STATES = {
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_REJECTED,
}
_ACTIONABLE_STATES = _TERMINAL_STATES | {TaskState.TASK_STATE_INPUT_REQUIRED}

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


def _status_text(task: Task) -> str:
    if task.status.HasField('message'):
        return get_message_text(task.status.message)
    return ''


async def _poll_until_actionable(client, task: Task) -> Task:
    while task.status.state not in _ACTIONABLE_STATES:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        task = await client.get_task(GetTaskRequest(id=task.id))
        text = _status_text(task)
        print(
            f'  poll: {_STATE_NAMES[task.status.state]}'
            + (f' — {text}' if text else '')
        )
    return task


async def main() -> None:
    opener = ' '.join(sys.argv[1:]) or DEFAULT_OPENER

    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(
            httpx_client=httpx_client, streaming=False, polling=True
        )
        client = ClientFactory(config).create(agent_card)

        print(f'Turn 1 (user):  {opener}')
        message = new_text_message(opener, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        task = None
        async for response in client.send_message(request):
            if response.HasField('task'):
                task = response.task

        if task is None:
            print('Agent did not return a task.')
            return

        print(f'Task {task.id} submitted, status: {_STATE_NAMES[task.status.state]}')
        task = await _poll_until_actionable(client, task)

        if task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
            question = _status_text(task)
            print(f'\nTurn 1 (agent, INPUT_REQUIRED): {question}\n')

            print(f'Turn 2 (user):  {FLIGHT_CHOICE_REPLY}')
            message = new_text_message(
                FLIGHT_CHOICE_REPLY,
                context_id=task.context_id,
                task_id=task.id,
                role=Role.ROLE_USER,
            )
            request = SendMessageRequest(message=message)

            async for response in client.send_message(request):
                if response.HasField('task'):
                    task = response.task

            print(f'Task resumed, status: {_STATE_NAMES[task.status.state]}')
            task = await _poll_until_actionable(client, task)

        print()
        if task.status.state == TaskState.TASK_STATE_COMPLETED:
            # By now the task carries two artifacts — the flight options
            # from the first phase, and the final confirmation from the
            # second. Only the latter is the actual result.
            for artifact in task.artifacts:
                if artifact.name == 'booking-confirmation':
                    print(get_artifact_text(artifact))
        elif task.status.HasField('message'):
            print(get_message_text(task.status.message))
        else:
            print(f'Task ended in state: {_STATE_NAMES[task.status.state]}')

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
