"""LLM-based parsing of an ongoing, multi-turn restaurant-reservation conversation.

Unlike the other agents' parsers, this one is handed the *entire*
conversation so far on every turn, not just the latest message — it has to
notice what earlier turns already established and only flag what's still
genuinely missing.
"""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_SYSTEM_PROMPT = (
    'You parse an ongoing restaurant-reservation conversation into '
    "structured data. You'll be given every message the user has sent so "
    'far, oldest first. Extract the restaurant (a specific name, or a '
    'cuisine/area if no name was given), the date, the time, and the party '
    "size. Later messages fill in what earlier ones left out — don't "
    "forget something just because it was mentioned a turn ago. If "
    "something genuinely hasn't been provided anywhere yet, phrase it as a "
    "short, specific question in `missing_info` (e.g. 'What time would "
    "you like?') instead of guessing."
)

_RESPONSE_SCHEMA = {
    'name': 'reservation_request',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'restaurant': {
                'type': ['string', 'null'],
                'description': 'Restaurant name, or cuisine/area if no name was given, or null if unknown.',
            },
            'date': {
                'type': ['string', 'null'],
                'description': 'Reservation date (exact or fuzzy), or null if not mentioned.',
            },
            'time': {
                'type': ['string', 'null'],
                'description': 'Reservation time, or null if not mentioned.',
            },
            'party_size': {
                'type': ['integer', 'null'],
                'description': 'Number of people, or null if not mentioned.',
            },
            'missing_info': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "Ready-to-ask questions for whatever's still missing. Empty if nothing is missing.",
            },
        },
        'required': [
            'restaurant',
            'date',
            'time',
            'party_size',
            'missing_info',
        ],
        'additionalProperties': False,
    },
}


class ReservationRequest(BaseModel):
    restaurant: str | None
    date: str | None
    time: str | None
    party_size: int | None
    missing_info: list[str]


async def parse_reservation_request(conversation_so_far: str) -> ReservationRequest:
    """Uses an LLM to extract reservation details from the conversation so far."""
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': conversation_so_far},
        ],
        response_format={
            'type': 'json_schema',
            'json_schema': _RESPONSE_SCHEMA,
        },
    )
    data = json.loads(completion.choices[0].message.content)
    return ReservationRequest(**data)
