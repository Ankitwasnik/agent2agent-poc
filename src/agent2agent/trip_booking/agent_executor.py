"""Trip Booking Agent — long-running work with a mid-task pause for input.

Combines two patterns this PoC only demonstrated separately until now: real
long-running work (WORKING for several real seconds, pollable — like
Itinerary Planning) and a mid-task pause for human input
(`TASK_STATE_INPUT_REQUIRED` — like Restaurant Reservation). Here they
compose: the agent searches for flights (genuinely slow), pauses to ask
which option the traveler wants, then resumes and does MORE real work
(booking a hotel, finalizing) before completing.

Which stage a given call is resuming into is derived from the task's own
state, not extra bookkeeping: if a `flight-options` artifact already exists
on the task, this call is answering that pause, not starting fresh.
"""

import asyncio

from a2a.helpers.proto_helpers import (
    get_artifact_text,
    get_message_text,
    new_task_from_user_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import Role, Task, TaskState

from agent2agent.trip_booking.options_generator import (
    FlightOption,
    choose_flight_option,
    generate_flight_options,
    generate_hotel_option,
)
from agent2agent.trip_booking.query_parser import parse_trip_details

_SEARCH_DELAY_SECONDS = 4
_FINALIZE_DELAY_SECONDS = 4
_FLIGHT_OPTIONS_ARTIFACT_ID = 'flight-options'


def _format_flight_options(options: list[FlightOption]) -> str:
    lines = []
    for index, option in enumerate(options, start=1):
        stop_desc = 'direct' if option.stops == 0 else f'{option.stops} stop(s)'
        lines.append(
            f'  {index}. {option.airline} — ${option.price_usd:.0f} — '
            f'{option.duration} ({stop_desc})'
        )
    return '\n'.join(lines)


def _user_turns_text(history: list, latest_message) -> str:
    messages = list(history)
    messages.append(latest_message)
    return '\n'.join(
        f'- {get_message_text(m)}' for m in messages if m.role == Role.ROLE_USER
    )


class TripBookingAgentExecutor(AgentExecutor):
    """Books a flight + hotel, pausing mid-task for a flight choice."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        is_first_turn = context.current_task is None

        if is_first_turn:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        current_task = context.current_task

        has_flight_options = current_task is not None and any(
            artifact.artifact_id == _FLIGHT_OPTIONS_ARTIFACT_ID
            for artifact in current_task.artifacts
        )

        if has_flight_options:
            await self._resume_after_flight_choice(context, updater, current_task)
        else:
            await self._search_flights_and_pause(context, updater, current_task)

    async def _search_flights_and_pause(
        self,
        context: RequestContext,
        updater: TaskUpdater,
        current_task: Task | None,
    ) -> None:
        conversation_so_far = _user_turns_text(
            current_task.history if current_task else [], context.message
        )

        await updater.start_work()

        try:
            parsed = await parse_trip_details(conversation_so_far)
        except Exception as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Couldn't process that: {exc}")]
                )
            )
            return

        missing = list(parsed.missing_info)
        if not parsed.missing_info:
            # Defensive backstop only: the LLM should have flagged this itself.
            if not parsed.destination:
                missing.append('What destination?')
            if not parsed.budget_usd:
                missing.append("What's your budget?")

        if missing:
            await updater.requires_input(
                updater.new_agent_message([new_text_part(' '.join(missing))])
            )
            return

        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            message=updater.new_agent_message(
                [new_text_part(f'Searching flights to {parsed.destination}...')]
            ),
        )
        # Simulate the time a real flight search would take.
        await asyncio.sleep(_SEARCH_DELAY_SECONDS)

        try:
            options = await generate_flight_options(
                parsed.destination, parsed.budget_usd
            )
        except Exception as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Couldn't search flights: {exc}")]
                )
            )
            return

        options_text = _format_flight_options(options)
        await updater.add_artifact(
            [new_text_part(options_text)],
            artifact_id=_FLIGHT_OPTIONS_ARTIFACT_ID,
            name='Flight Options',
        )
        await updater.requires_input(
            updater.new_agent_message(
                [
                    new_text_part(
                        'I found two flight options:\n'
                        + options_text
                        + '\n\nWhich one would you like — 1 or 2?'
                    )
                ]
            )
        )

    async def _resume_after_flight_choice(
        self,
        context: RequestContext,
        updater: TaskUpdater,
        current_task: Task,
    ) -> None:
        options_artifact = next(
            artifact
            for artifact in current_task.artifacts
            if artifact.artifact_id == _FLIGHT_OPTIONS_ARTIFACT_ID
        )
        options_text = get_artifact_text(options_artifact)
        reply_text = context.get_user_input()
        conversation_so_far = _user_turns_text(current_task.history, context.message)

        await updater.start_work()

        try:
            parsed = await parse_trip_details(conversation_so_far)
            chosen_number = await choose_flight_option(options_text, reply_text)
        except Exception as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Couldn't finalize the booking: {exc}")]
                )
            )
            return

        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            message=updater.new_agent_message(
                [new_text_part('Finalizing your booking...')]
            ),
        )
        # Simulate the time booking the hotel and confirming everything
        # would take, beyond the LLM call itself.
        await asyncio.sleep(_FINALIZE_DELAY_SECONDS)

        try:
            hotel = await generate_hotel_option(parsed.destination)
        except Exception as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Couldn't book a hotel: {exc}")]
                )
            )
            return

        chosen_line = options_text.splitlines()[chosen_number - 1].strip()
        confirmation = (
            'Booking confirmed!\n'
            f'  Flight : {chosen_line}\n'
            f'  Hotel  : {hotel.hotel_name} — ${hotel.price_per_night_usd:.0f}/night'
        )
        await updater.add_artifact(
            [new_text_part(confirmation)], name='booking-confirmation'
        )
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()
