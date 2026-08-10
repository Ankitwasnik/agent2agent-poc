"""Client for the Visa/Travel-Requirements Agent — demonstrates push notifications.

Registers a local webhook URL when sending the request, then does nothing
but wait: no polling loop, no held-open stream. The agent's server calls
back to this client's own tiny HTTP endpoint whenever the task updates.
"""

import asyncio
import sys

import httpx
import uvicorn
from google.protobuf.json_format import ParseDict
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import (
    get_artifact_text,
    get_message_text,
    new_text_message,
)
from a2a.types.a2a_pb2 import (
    Role,
    SendMessageRequest,
    StreamResponse,
    TaskPushNotificationConfig,
    TaskState,
)

AGENT_URL = 'http://localhost:9004'
WEBHOOK_HOST = 'localhost'
WEBHOOK_PORT = 8004
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f'http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_PATH}'

DEFAULT_QUERY = 'Do I need a visa? I am a US citizen traveling to Vietnam.'
WAIT_TIMEOUT_SECONDS = 60

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


def _print_pushed_event(response: StreamResponse) -> None:
    if response.HasField('task'):
        task = response.task
        print(f'[webhook] task — status: {_STATE_NAMES[task.status.state]}')
    elif response.HasField('status_update'):
        status = response.status_update.status
        text = (
            get_message_text(status.message)
            if status.HasField('message')
            else ''
        )
        print(
            f'[webhook] status: {_STATE_NAMES[status.state]}'
            + (f': {text}' if text else '')
        )
    elif response.HasField('artifact_update'):
        print(
            f'[webhook] artifact:\n{get_artifact_text(response.artifact_update.artifact)}'
        )
    elif response.HasField('message'):
        print(f'[webhook] message: {get_message_text(response.message)}')


def _is_terminal(response: StreamResponse) -> bool:
    if response.HasField('task'):
        return response.task.status.state in _TERMINAL_STATES
    if response.HasField('status_update'):
        return response.status_update.status.state in _TERMINAL_STATES
    return False


async def main() -> None:
    query = ' '.join(sys.argv[1:]) or DEFAULT_QUERY
    completion_event = asyncio.Event()

    async def handle_webhook(request: Request) -> Response:
        body = await request.json()
        response = ParseDict(body, StreamResponse())
        _print_pushed_event(response)
        if _is_terminal(response):
            completion_event.set()
        return Response(status_code=200)

    webhook_app = Starlette(
        routes=[Route(WEBHOOK_PATH, handle_webhook, methods=['POST'])]
    )
    uvicorn_config = uvicorn.Config(
        webhook_app, host=WEBHOOK_HOST, port=WEBHOOK_PORT, log_level='warning'
    )
    webhook_server = uvicorn.Server(uvicorn_config)
    webhook_task = asyncio.create_task(webhook_server.serve())
    while not webhook_server.started:
        await asyncio.sleep(0.05)

    try:
        async with httpx.AsyncClient() as httpx_client:
            resolver = A2ACardResolver(httpx_client, AGENT_URL)
            agent_card = await resolver.get_agent_card()

            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=False,
                polling=True,
                push_notification_config=TaskPushNotificationConfig(
                    url=WEBHOOK_URL
                ),
            )
            client = ClientFactory(config).create(agent_card)

            message = new_text_message(query, role=Role.ROLE_USER)
            request = SendMessageRequest(message=message)

            print(f'Query: {query}')
            print(f'Registering webhook: {WEBHOOK_URL}')
            print('Sending request...\n')

            task = None
            async for response in client.send_message(request):
                if response.HasField('task'):
                    task = response.task

            if task is None:
                print('Agent did not return a task.')
                return

            print(
                f'Task {task.id} submitted, status: {_STATE_NAMES[task.status.state]}'
            )
            print(
                'Waiting for push notifications '
                '(no polling loop, no open stream held by this client)...\n'
            )

            try:
                await asyncio.wait_for(
                    completion_event.wait(), timeout=WAIT_TIMEOUT_SECONDS
                )
            except TimeoutError:
                print(
                    f'\nTimed out after {WAIT_TIMEOUT_SECONDS}s waiting for a push notification.'
                )

            await client.close()
    finally:
        webhook_server.should_exit = True
        await webhook_task


if __name__ == '__main__':
    asyncio.run(main())
