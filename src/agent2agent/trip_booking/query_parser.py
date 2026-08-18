"""LLM-based parsing of an ongoing, multi-turn trip-booking conversation."""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_SYSTEM_PROMPT = (
    'You parse an ongoing trip-booking conversation into structured data. '
    "You'll be given every message the user has sent so far, oldest "
    'first. Extract the destination and the budget in US dollars. Later '
    "messages fill in what earlier ones left out. If something genuinely "
    "hasn't been provided anywhere yet, phrase it as a short, specific "
    'question in `missing_info` instead of guessing.'
)

_RESPONSE_SCHEMA = {
    'name': 'trip_details',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'destination': {
                'type': ['string', 'null'],
                'description': 'Destination city/region, or null if unknown.',
            },
            'budget_usd': {
                'type': ['number', 'null'],
                'description': 'Total budget in US dollars, or null if not mentioned.',
            },
            'missing_info': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "Ready-to-ask questions for whatever's still missing. Empty if nothing is missing.",
            },
        },
        'required': ['destination', 'budget_usd', 'missing_info'],
        'additionalProperties': False,
    },
}


class TripDetails(BaseModel):
    destination: str | None
    budget_usd: float | None
    missing_info: list[str]


async def parse_trip_details(conversation_so_far: str) -> TripDetails:
    """Uses an LLM to extract destination/budget from the conversation so far."""
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
    return TripDetails(**data)
