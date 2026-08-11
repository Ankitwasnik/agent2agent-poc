"""Failure-mode demo: task paused indefinitely (README Section 4d).

A2A gives you `tasks/cancel` and a loud `TaskNotCancelableError` — but it
doesn't decide *when* to give up on a slow task. That's the client's own
timeout policy. This demo submits an itinerary-planning task, polls with a
budget shorter than the agent's actual work time, cancels once the budget
is blown, and then tries to cancel the same (now-terminal) task again to
show the explicit error instead of a silent no-op.
"""

import asyncio

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import new_text_message
from a2a.types.a2a_pb2 import (
    CancelTaskRequest,
    GetTaskRequest,
    Role,
    SendMessageRequest,
    TaskState,
)
from a2a.utils.errors import TaskNotCancelableError

AGENT_URL = 'http://localhost:9002'
QUERY = 'Plan a 3-day itinerary for Tokyo focused on food and temples'

# Deliberately shorter than the agent's own simulated planning delay so the
# client's timeout policy is guaranteed to trigger for this demo.
CLIENT_TIMEOUT_BUDGET_SECONDS = 3
POLL_INTERVAL_SECONDS = 1

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
            httpx_client=httpx_client, streaming=False, polling=True
        )
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(QUERY, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {QUERY}')
        print(f'Client timeout budget: {CLIENT_TIMEOUT_BUDGET_SECONDS}s\n')

        task = None
        async for response in client.send_message(request):
            if response.HasField('task'):
                task = response.task

        if task is None:
            print('Agent did not return a task.')
            return

        print(f'Task {task.id} submitted, status: {_STATE_NAMES[task.status.state]}')

        elapsed = 0
        while (
            task.status.state not in _TERMINAL_STATES
            and elapsed < CLIENT_TIMEOUT_BUDGET_SECONDS
        ):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
            task = await client.get_task(GetTaskRequest(id=task.id))
            print(f'  poll at {elapsed}s: status: {_STATE_NAMES[task.status.state]}')

        if task.status.state in _TERMINAL_STATES:
            print(
                f'\nTask reached a terminal state within budget '
                f'({_STATE_NAMES[task.status.state]}) — nothing to cancel. '
                 'Lower CLIENT_TIMEOUT_BUDGET_SECONDS to force the timeout path.'
            )
            await client.close()
            return

        print(
            f'\n--- Exceeded client timeout budget of '
            f'{CLIENT_TIMEOUT_BUDGET_SECONDS}s — canceling task {task.id} ---'
        )
        canceled_task = await client.cancel_task(CancelTaskRequest(id=task.id))
        print(f'Task status after cancel: {_STATE_NAMES[canceled_task.status.state]}')

        print(
            f'\n--- Attempting to cancel the same task again '
            '(it is already terminal) ---'
        )
        try:
            await client.cancel_task(CancelTaskRequest(id=task.id))
            print('UNEXPECTED: second cancel succeeded.')
        except TaskNotCancelableError as exc:
            print(f'TaskNotCancelableError (explicit, not a silent no-op): {exc.message}')

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
