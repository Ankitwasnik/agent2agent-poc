"""Failure-mode demo: dropped connection + resubscribe (README Section 4c/4e).

Opens an SSE stream to the Hotel Search agent, deliberately drops the
connection partway through the task (simulating a network blip or a client
that just crashed), waits a moment while the agent keeps working in the
background, then resubscribes to the SAME task. Confirms `tasks/subscribe`
replays a full current snapshot before resuming live updates — the client
never actually lost anything, even though its connection did.
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
    StreamResponse,
    SubscribeToTaskRequest,
    TaskState,
)
from a2a.utils.errors import InvalidParamsError

AGENT_URL = 'http://localhost:9003'
QUERY = (
    'Find hotels in Tokyo for 2 guests, checking in 2026-09-10 and '
    'checking out 2026-09-14'
)
EVENTS_BEFORE_DROP = 3  # task ack + first status + first artifact, then drop
GAP_SECONDS = 15  # how long we stay disconnected while the agent keeps working

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


def _print_event(prefix: str, response: StreamResponse) -> None:
    if response.HasField('task'):
        task = response.task
        print(
            f'{prefix} task {task.id} — status: '
            f'{_STATE_NAMES[task.status.state]}, artifacts so far: {len(task.artifacts)}'
        )
    elif response.HasField('status_update'):
        status = response.status_update.status
        text = (
            get_message_text(status.message)
            if status.HasField('message')
            else ''
        )
        print(
            f'{prefix} status: {_STATE_NAMES[status.state]}'
            + (f': {text}' if text else '')
        )
    elif response.HasField('artifact_update'):
        print(
            f'{prefix} artifact: {get_artifact_text(response.artifact_update.artifact)}'
        )


def _is_terminal(response: StreamResponse) -> bool:
    if response.HasField('task'):
        return response.task.status.state in _TERMINAL_STATES
    if response.HasField('status_update'):
        return response.status_update.status.state in _TERMINAL_STATES
    return False


async def main() -> None:
    async with httpx.AsyncClient(timeout=None) as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(httpx_client=httpx_client, streaming=True)
        client = ClientFactory(config).create(agent_card)

        message = new_text_message(QUERY, role=Role.ROLE_USER)
        request = SendMessageRequest(message=message)

        print(f'Query: {QUERY}')
        print('Opening SSE stream...\n')

        task_id = None
        stream = client.send_message(request)
        count = 0
        finished_before_drop = False
        async for response in stream:
            _print_event('[live]                     ', response)
            if response.HasField('task'):
                task_id = response.task.id
            count += 1
            if _is_terminal(response):
                finished_before_drop = True
                break
            if count >= EVENTS_BEFORE_DROP:
                break

        if task_id is None:
            print('Never got a task id — aborting demo.')
            await client.close()
            return

        if finished_before_drop:
            print(
                '\nTask finished before we had a chance to drop the '
                'connection — run again to catch it mid-task.'
            )
            await client.close()
            return

        print('\n--- Simulating a dropped connection (closing the stream early) ---')
        await stream.aclose()

        print(
            f'--- Disconnected for {GAP_SECONDS}s. The agent keeps working '
            'in the background, unaware the client left. ---\n'
        )
        await asyncio.sleep(GAP_SECONDS)

        print(f'--- Resubscribing to task {task_id} ---')
        try:
            first = True
            async for response in client.subscribe(
                SubscribeToTaskRequest(id=task_id)
            ):
                label = (
                    '[resubscribe: full snapshot]'
                    if first
                    else '[resubscribe: live]         '
                )
                _print_event(label, response)
                first = False
                if _is_terminal(response):
                    break
        except InvalidParamsError as exc:
            # The task finished (and had no subscribers) during the gap, so
            # the server already evicted it from active tracking — there's
            # nothing left to "subscribe" to. tasks/get still works, since it
            # reads the persisted task store directly rather than active
            # tracking. A real client should fall back the same way.
            print(
                f'Resubscribe failed ({exc.message}) — the task finished '
                'and was cleaned up while we were disconnected. Falling '
                'back to tasks/get for the final state:\n'
            )
            task = await client.get_task(GetTaskRequest(id=task_id))
            print(f'[tasks/get] status: {_STATE_NAMES[task.status.state]}')
            for artifact in task.artifacts:
                print(f'[tasks/get] artifact: {get_artifact_text(artifact)}')

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
