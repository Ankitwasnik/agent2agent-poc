"""Hotel Search Agent — demonstrates the SSE streaming pattern.

Each hotel option is found by its own LLM call. That gives each result
genuine, separate latency, so streaming a TaskArtifactUpdateEvent chunk as
each one arrives is showing real incremental progress rather than slicing
up a single response for effect — the client keeps one SSE connection open
and watches it happen, rather than polling or waiting for a webhook.
"""

from a2a.helpers.proto_helpers import new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import TaskState

from agent2agent.hotel_search.offer_generator import generate_hotel_offer
from agent2agent.hotel_search.query_parser import parse_hotel_query

_DEFAULT_NUM_HOTELS = 3
_MAX_NUM_HOTELS = 10  # cap so an open-ended count doesn't trigger unbounded LLM calls


def _format_hotel(hotel_name: str, price_per_night_usd: float) -> str:
    return f'  {hotel_name} — ${price_per_night_usd:.0f}/night'


class HotelSearchAgentExecutor(AgentExecutor):
    """Streams a TaskArtifactUpdateEvent chunk as each hotel option is found."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        try:
            parsed = await parse_hotel_query(context.get_user_input())
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
            if not parsed.checkin:
                missing.append('a check-in date')
            if not parsed.checkout:
                missing.append('a check-out date')

        if missing:
            message = updater.new_agent_message(
                [
                    new_text_part(
                        'I need a bit more information before I can search for hotels:\n'
                        + '\n'.join(f'  - {item}' for item in missing)
                    )
                ]
            )
            await updater.complete(message=message)
            return

        guests = parsed.guests or 1
        num_hotels = max(
            1, min(parsed.num_hotels or _DEFAULT_NUM_HOTELS, _MAX_NUM_HOTELS)
        )

        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            message=updater.new_agent_message(
                [new_text_part(f'Searching for hotels in {parsed.destination}...')]
            ),
        )

        found_names: list[str] = []
        for index in range(num_hotels):
            try:
                offer = await generate_hotel_offer(
                    parsed.destination,
                    parsed.checkin,
                    parsed.checkout,
                    guests,
                    exclude=found_names,
                )
            except Exception as exc:
                await updater.failed(
                    updater.new_agent_message(
                        [new_text_part(f"Couldn't fetch hotel results: {exc}")]
                    )
                )
                return

            found_names.append(offer.hotel_name)
            await updater.add_artifact(
                [new_text_part(_format_hotel(offer.hotel_name, offer.price_per_night_usd))],
                artifact_id='hotel-results',
                name='Hotel Options',
                append=index > 0,
                last_chunk=index == num_hotels - 1,
            )

        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()
