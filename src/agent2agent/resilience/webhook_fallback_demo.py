"""Failure-mode demo: webhook never arrives (README Section 4d).

Push-notification delivery is best-effort by design — the server logs a
failed POST and moves on; it does not retry or guarantee delivery. If the
client's webhook endpoint is unreachable (crashed, firewalled, wrong URL),
the client has to notice on its own and fall back to something else, since
A2A won't do that for you. This demo registers a webhook nobody is
listening on, waits with a timeout, then falls back to polling `tasks/get`
directly.
"""

import asyncio

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
    TaskPushNotificationConfig,
    TaskState,
)

AGENT_URL = 'http://localhost:9004'
# Nothing is listening here — every push attempt the server makes will fail.
UNREACHABLE_WEBHOOK_URL = 'http://localhost:8099/webhook'
QUERY = 'Do I need a visa? I am a US citizen traveling to Vietnam.'

WEBHOOK_WAIT_TIMEOUT_SECONDS = 15
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
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(
            httpx_client=httpx_client,
            streaming=False,
            polling=True,
            push_notification_config=TaskPushNotificationConfig(
                url=UNREACHABLE_WEBHOOK_URL
            ),
        )
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(QUERY, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {QUERY}')
        print(f'Registering an UNREACHABLE webhook: {UNREACHABLE_WEBHOOK_URL}')
        print(
            '(nothing is listening there on purpose — every push attempt '
            'will fail)\n'
        )

        task = None
        async for response in client.send_message(request):
            if response.HasField('task'):
                task = response.task

        if task is None:
            print('Agent did not return a task.')
            return

        print(f'Task {task.id} submitted, status: {_STATE_NAMES[task.status.state]}')
        print(
            f'Waiting up to {WEBHOOK_WAIT_TIMEOUT_SECONDS}s for a push '
            'notification that will never come...\n'
        )
        await asyncio.sleep(WEBHOOK_WAIT_TIMEOUT_SECONDS)

        print('--- No push notification received. Falling back to polling. ---\n')

        while task.status.state not in _TERMINAL_STATES:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            task = await client.get_task(GetTaskRequest(id=task.id))
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
