"""Visa/Travel-Requirements Agent — demonstrates the push-notification pattern.

Checking visa requirements stands in for a slow, human-in-the-loop process
(e.g. an embassy/document review) — too long to poll for or hold a stream
open across. The agent enqueues a Task and works in the background exactly
like the polling agent; the difference is entirely in transport. If the
client attached a push notification config to its request, the framework
POSTs each TaskStatusUpdateEvent/TaskArtifactUpdateEvent to that URL on its
own — no special code needed here beyond the normal Task + TaskUpdater flow.
"""

import asyncio

from a2a.helpers.proto_helpers import new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import TaskState

from agent2agent.visa_requirements.query_parser import parse_visa_query
from agent2agent.visa_requirements.requirements_generator import (
    draft_visa_requirements,
)

_REVIEW_DELAY_SECONDS = 6

_DISCLAIMER = (
    '\n\n(Simulated for this demo — verify with official sources before travel.)'
)


class VisaRequirementsAgentExecutor(AgentExecutor):
    """Long-running visa check: Task + status updates, pushed to a webhook."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        try:
            parsed = await parse_visa_query(context.get_user_input())
        except Exception as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Couldn't process that request: {exc}")]
                )
            )
            return

        missing = list(parsed.missing_info)
        if not parsed.missing_info:
            # Defensive backstop only: the LLM should have flagged this itself.
            if not parsed.nationality:
                missing.append("the traveler's nationality")
            if not parsed.destination:
                missing.append('the destination country')

        if missing:
            message = updater.new_agent_message(
                [
                    new_text_part(
                        'I need a bit more information before I can check visa requirements:\n'
                        + '\n'.join(f'  - {item}' for item in missing)
                    )
                ]
            )
            await updater.complete(message=message)
            return

        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            message=updater.new_agent_message(
                [
                    new_text_part(
                        f'Checking visa requirements for a {parsed.nationality} '
                        f'citizen traveling to {parsed.destination}...'
                    )
                ]
            ),
        )

        # Simulate the time a real embassy/document review would take — long
        # enough that holding an SSE stream or polling loop open for it would
        # be wasteful; a push notification when it's done fits better.
        await asyncio.sleep(_REVIEW_DELAY_SECONDS)

        try:
            summary = await draft_visa_requirements(
                parsed.nationality, parsed.destination
            )
        except Exception as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Couldn't determine requirements: {exc}")]
                )
            )
            return

        await updater.add_artifact(
            [new_text_part(summary + _DISCLAIMER)],
            name='visa-requirements',
        )
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()
