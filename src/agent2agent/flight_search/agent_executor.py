"""Flight Search Agent — demonstrates the synchronous request/response pattern.

The agent looks up flights for a given origin/destination/date and replies
with a single Message. Per the A2A spec, enqueueing exactly one Message (as
opposed to a Task + status updates) tells the framework this is an immediate,
one-shot interaction — there is nothing to poll, stream, or push updates for.

Query understanding is delegated to an LLM (see query_parser.py): it maps
free-form requests like "the bay area to nyc sometime next month" onto
structured origin/destination/date fields before the deterministic mock
flight lookup runs. That reasoning step is what makes this an actual agent
rather than a fixed request/response script.
"""

from a2a.helpers.proto_helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types.a2a_pb2 import Role

from agent2agent.flight_search.query_parser import parse_flight_query

_MOCK_FLIGHTS = {
    ('SFO', 'JFK'): [
        {'carrier': 'AA', 'flight_no': 'AA101', 'depart': '08:00', 'arrive': '16:25', 'price': 342},
        {'carrier': 'UA', 'flight_no': 'UA245', 'depart': '13:10', 'arrive': '21:35', 'price': 289},
    ],
    ('JFK', 'SFO'): [
        {'carrier': 'AA', 'flight_no': 'AA102', 'depart': '18:00', 'arrive': '21:22', 'price': 355},
        {'carrier': 'DL', 'flight_no': 'DL876', 'depart': '09:45', 'arrive': '13:05', 'price': 301},
    ],
    ('LAX', 'ORD'): [
        {'carrier': 'UA', 'flight_no': 'UA512', 'depart': '07:15', 'arrive': '13:20', 'price': 210},
    ],
}

_GENERIC_FLIGHTS = [
    {'carrier': 'ZZ', 'flight_no': 'ZZ100', 'depart': '09:00', 'arrive': '11:30', 'price': 199},
    {'carrier': 'ZZ', 'flight_no': 'ZZ200', 'depart': '15:45', 'arrive': '18:10', 'price': 249},
]


def _search_flights(origin: str, destination: str) -> list[dict]:
    return _MOCK_FLIGHTS.get((origin, destination), _GENERIC_FLIGHTS)


def _format_flights(
    origin: str, destination: str, date: str, flights: list[dict]
) -> str:
    lines = [f'Flights from {origin} to {destination} on {date}:']
    for f in flights:
        lines.append(
            f"  {f['carrier']} {f['flight_no']}  "
            f"depart {f['depart']} -> arrive {f['arrive']}  (${f['price']})"
        )
    return '\n'.join(lines)


class FlightSearchAgentExecutor(AgentExecutor):
    """Synchronous flight lookup: one request in, one Message out."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        query = context.get_user_input()

        try:
            parsed = await parse_flight_query(query)
        except Exception as exc:
            reply_text = (
                f"Sorry, I couldn't process that request right now: {exc}"
            )
        else:
            missing = list(parsed.missing_info)
            if not parsed.missing_info:
                # Defensive backstop only: the LLM should have flagged this
                # itself, but don't let a null field slip through silently.
                if not parsed.origin_iata:
                    missing.append('a clear origin airport or city')
                if not parsed.destination_iata:
                    missing.append('a clear destination airport or city')

            if missing:
                reply_text = 'I need a bit more information before I can search:\n' + '\n'.join(
                    f'  - {item}' for item in missing
                )
            else:
                origin = parsed.origin_iata.upper()
                destination = parsed.destination_iata.upper()
                date = parsed.travel_date or 'any date'
                reply_text = _format_flights(
                    origin, destination, date, _search_flights(origin, destination)
                )

        reply = new_text_message(
            reply_text,
            context_id=context.context_id,
            task_id=context.task_id,
            role=Role.ROLE_AGENT,
        )
        await event_queue.enqueue_event(reply)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        # Nothing to cancel: execute() already returned by the time any
        # cancellation request could arrive for this synchronous agent.
        pass
