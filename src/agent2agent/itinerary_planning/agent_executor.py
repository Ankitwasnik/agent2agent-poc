"""Itinerary Planning Agent — demonstrates the polling pattern.

Drafting a day-by-day itinerary takes a noticeable amount of time (an LLM
call, plus a simulated planning delay for "checking availability" etc.).
Per the A2A spec, enqueueing a Task (rather than a single Message) followed
by TaskStatusUpdateEvent/TaskArtifactUpdateEvent updates tells the framework
this is a long-running interaction: the client gets the Task back right
away and is expected to check in later via tasks/get instead of blocking or
holding a stream open.
"""

import asyncio

from a2a.helpers.proto_helpers import new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater

from agent2agent.itinerary_planning.itinerary_generator import (
    draft_itinerary,
    parse_itinerary_request,
)

_PLANNING_DELAY_SECONDS = 6


class ItineraryPlanningAgentExecutor(AgentExecutor):
    """Long-running itinerary drafting: Task + status updates, polled by the client."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        try:
            parsed = await parse_itinerary_request(context.get_user_input())
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
            if not parsed.destination:
                missing.append('a destination city')
            if not parsed.num_days:
                missing.append('how many days the trip should be')

        if missing:
            message = updater.new_agent_message(
                [
                    new_text_part(
                        'I need a bit more information before I can plan this trip:\n'
                        + '\n'.join(f'  - {item}' for item in missing)
                    )
                ]
            )
            await updater.complete(message=message)
            return

        # Simulate the time a real planning pipeline would take beyond the
        # LLM call itself (checking availability, cross-referencing hours,
        # etc.) — long enough that a client polling every few seconds sees
        # more than one WORKING check-in before completion.
        await asyncio.sleep(_PLANNING_DELAY_SECONDS)

        itinerary_text = await draft_itinerary(
            parsed.destination, parsed.num_days, parsed.interests
        )

        await updater.add_artifact(
            [new_text_part(itinerary_text)],
            name='itinerary',
        )
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()
