"""LLM-based free-form flight query parsing.

This is what makes the Flight Search Agent an actual *agent* rather than a
regex trick: the LLM does the reasoning about what the user meant (mapping
"the bay area" to SFO, resolving fuzzy dates, noticing when something's
missing) before the deterministic mock flight lookup ever runs.
"""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_SYSTEM_PROMPT = (
    'You parse free-form flight search requests into structured data. '
    'Map cities/regions to their primary 3-letter IATA airport code '
    "(e.g. 'the bay area' -> SFO, 'nyc' -> JFK, 'LA' -> LAX, 'chicago' -> ORD, "
    "'boston' -> BOS, 'miami' -> MIA). If the origin, destination, or a travel "
    'date genuinely cannot be determined from the request, list each missing '
    'piece in `missing_info` in plain language instead of guessing.'
)

_RESPONSE_SCHEMA = {
    'name': 'flight_query',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'origin_iata': {
                'type': ['string', 'null'],
                'description': '3-letter IATA code for the origin airport, or null if unknown.',
            },
            'destination_iata': {
                'type': ['string', 'null'],
                'description': '3-letter IATA code for the destination airport, or null if unknown.',
            },
            'travel_date': {
                'type': ['string', 'null'],
                'description': "The travel date as stated by the user (exact or fuzzy, e.g. 'next month'), or null if not mentioned.",
            },
            'missing_info': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "Plain-language list of what's needed before a search can run. Empty if nothing is missing.",
            },
        },
        'required': [
            'origin_iata',
            'destination_iata',
            'travel_date',
            'missing_info',
        ],
        'additionalProperties': False,
    },
}


class FlightQuery(BaseModel):
    origin_iata: str | None
    destination_iata: str | None
    travel_date: str | None
    missing_info: list[str]


async def parse_flight_query(text: str) -> FlightQuery:
    """Uses an LLM to extract a structured flight query from free-form text."""
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
    return FlightQuery(**data)
