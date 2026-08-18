"""Client for the Restaurant Reservation Agent — demonstrates multi-turn
interaction via `TASK_STATE_INPUT_REQUIRED`.

Runs a short, scripted conversation: a deliberately incomplete opener, then
a follow-up filling in whatever the agent asked for — sent with the SAME
task ID and context ID, continuing the SAME task rather than starting a new
one. Each turn is one blocking call, exactly like the Flight Search
client — the difference is entirely in what the task itself does with it.
"""

import asyncio

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import (
    get_artifact_text,
    get_message_text,
    new_text_message,
)
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState

AGENT_URL = 'http://localhost:9005'

# A deliberately incomplete opener, then a follow-up filling in the rest.
SCRIPTED_TURNS = [
    "I'd like to book a table at Le Jardin for tomorrow evening.",
    '7:30 PM, for 4 people please.',
]

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
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client, AGENT_URL)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(
            httpx_client=httpx_client, streaming=False, polling=False
        )
        client = ClientFactory(config).create(agent_card)

        task_id = None
        context_id = None

        for turn_number, turn_text in enumerate(SCRIPTED_TURNS, start=1):
            print(f'Turn {turn_number} (user):  {turn_text}')

            message = new_text_message(
                turn_text,
                context_id=context_id,
                task_id=task_id,
                role=Role.ROLE_USER,
            )
            request = SendMessageRequest(message=message)

            task = None
            async for response in client.send_message(request):
                if response.HasField('task'):
                    task = response.task

            if task is None:
                print('  Agent did not return a task.')
                break

            task_id = task.id
            context_id = task.context_id
            state_name = _STATE_NAMES[task.status.state]

            if task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
                question = (
                    get_message_text(task.status.message)
                    if task.status.HasField('message')
                    else ''
                )
                print(f'Turn {turn_number} (agent, {state_name}): {question}\n')
            elif task.status.state == TaskState.TASK_STATE_COMPLETED:
                print(f'Turn {turn_number} (agent, {state_name}):')
                for artifact in task.artifacts:
                    print(get_artifact_text(artifact))
                break
            else:
                print(f'Turn {turn_number} (agent, {state_name}) — stopping.')
                break

        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
