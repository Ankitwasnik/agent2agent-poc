"""Restaurant Reservation Agent — demonstrates multi-turn interaction via
`TASK_STATE_INPUT_REQUIRED`.

Every other agent in this PoC resolves in a single call: either it has
everything it needs, or it gives up and asks for what's missing in one
final, terminal message. This one doesn't give up. If required details are
still missing after a given turn, the executor puts the task into
`INPUT_REQUIRED` and returns — yielding control back to the client without
ending the task. The client's next message, sent with the SAME task ID,
resumes the SAME conversation: the framework calls `execute()` again with
`context.current_task` now populated (including the first turn's history),
so the executor re-reads the *entire* conversation so far — not just the
latest message — to decide what's still missing.
"""

from a2a.helpers.proto_helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import Role

from agent2agent.restaurant_reservation.query_parser import (
    ReservationRequest,
    parse_reservation_request,
)


def _format_confirmation(parsed: ReservationRequest) -> str:
    return (
        'Reservation confirmed:\n'
        f'  Restaurant : {parsed.restaurant}\n'
        f'  Date       : {parsed.date}\n'
        f'  Time       : {parsed.time}\n'
        f'  Party size : {parsed.party_size}'
    )


class RestaurantReservationAgentExecutor(AgentExecutor):
    """Resolves a reservation over as many turns as it takes."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        is_first_turn = context.current_task is None

        if is_first_turn:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not is_first_turn:
            # Coming back from INPUT_REQUIRED: say so before re-parsing.
            await updater.start_work()

        prior_messages = (
            list(context.current_task.history) if context.current_task else []
        )
        prior_messages.append(context.message)
        conversation_so_far = '\n'.join(
            f'- {get_message_text(m)}'
            for m in prior_messages
            if m.role == Role.ROLE_USER
        )

        try:
            parsed = await parse_reservation_request(conversation_so_far)
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
            if not parsed.restaurant:
                missing.append('Which restaurant, cuisine, or area?')
            if not parsed.date:
                missing.append('What date?')
            if not parsed.time:
                missing.append('What time?')
            if not parsed.party_size:
                missing.append('How many people?')

        if missing:
            await updater.requires_input(
                updater.new_agent_message([new_text_part(' '.join(missing))])
            )
            return

        await updater.add_artifact(
            [new_text_part(_format_confirmation(parsed))],
            name='reservation-confirmation',
        )
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()
