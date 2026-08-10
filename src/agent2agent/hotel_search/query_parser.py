"""LLM-based free-form hotel query parsing."""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_SYSTEM_PROMPT = (
    'You parse free-form hotel search requests into structured data. '
    'Extract the destination city, the check-in date, the check-out date, '
    'and the number of guests. If any of these genuinely cannot be '
    'determined from the request, list each missing piece in `missing_info` '
    'in plain language instead of guessing. Also extract how many hotel '
    "options the user asked for (e.g. 'find me 10 hotels' -> 10), or null "
    "if they didn't say — this one is optional, never list it in "
    '`missing_info`.'
)

_RESPONSE_SCHEMA = {
    'name': 'hotel_query',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'destination': {
                'type': ['string', 'null'],
                'description': 'City/region to stay in, or null if unknown.',
            },
            'checkin': {
                'type': ['string', 'null'],
                'description': 'Check-in date as stated by the user (exact or fuzzy), or null if not mentioned.',
            },
            'checkout': {
                'type': ['string', 'null'],
                'description': 'Check-out date as stated by the user (exact or fuzzy), or null if not mentioned.',
            },
            'guests': {
                'type': ['integer', 'null'],
                'description': 'Number of guests, or null if not mentioned.',
            },
            'num_hotels': {
                'type': ['integer', 'null'],
                'description': 'How many hotel options the user asked for, or null if not specified.',
            },
            'missing_info': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "Plain-language list of what's needed before a search can run. Empty if nothing is missing.",
            },
        },
        'required': [
            'destination',
            'checkin',
            'checkout',
            'guests',
            'num_hotels',
            'missing_info',
        ],
        'additionalProperties': False,
    },
}


class HotelQuery(BaseModel):
    destination: str | None
    checkin: str | None
    checkout: str | None
    guests: int | None
    num_hotels: int | None
    missing_info: list[str]


async def parse_hotel_query(text: str) -> HotelQuery:
    """Uses an LLM to extract a structured hotel query from free-form text."""
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': text},
        ],
        response_format={'type': 'json_schema', 'json_schema': _RESPONSE_SCHEMA},
    )
    data = json.loads(completion.choices[0].message.content)
    return HotelQuery(**data)
