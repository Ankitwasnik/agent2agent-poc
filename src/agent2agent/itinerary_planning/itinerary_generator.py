"""LLM-based itinerary request parsing and drafting.

Two LLM calls, mirroring how a real planning agent would reason: first
understand what the traveler actually wants (destination, duration,
interests), then draft the plan itself.
"""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_PARSE_SYSTEM_PROMPT = (
    'You parse free-form trip-planning requests into structured data. '
    'Extract the destination city, the number of days for the trip, and any '
    'stated interests/themes (e.g. food, museums, hiking). If the destination '
    'or number of days genuinely cannot be determined, list each missing '
    'piece in `missing_info` in plain language instead of guessing.'
)

_PARSE_SCHEMA = {
    'name': 'itinerary_request',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'destination': {
                'type': ['string', 'null'],
                'description': 'City/region to visit, or null if unknown.',
            },
            'num_days': {
                'type': ['integer', 'null'],
                'description': 'Number of days for the trip, or null if unknown.',
            },
            'interests': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Stated interests/themes, empty if none mentioned.',
            },
            'missing_info': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "Plain-language list of what's needed before an itinerary can be drafted. Empty if nothing is missing.",
            },
        },
        'required': [
            'destination',
            'num_days',
            'interests',
            'missing_info',
        ],
        'additionalProperties': False,
    },
}


class ItineraryRequest(BaseModel):
    destination: str | None
    num_days: int | None
    interests: list[str]
    missing_info: list[str]


async def parse_itinerary_request(text: str) -> ItineraryRequest:
    """Uses an LLM to extract destination/duration/interests from free-form text."""
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _PARSE_SYSTEM_PROMPT},
            {'role': 'user', 'content': text},
        ],
        response_format={'type': 'json_schema', 'json_schema': _PARSE_SCHEMA},
    )
    data = json.loads(completion.choices[0].message.content)
    return ItineraryRequest(**data)


_DRAFT_SYSTEM_PROMPT = (
    'You are a travel itinerary planner. Given a destination, a number of '
    'days, and optional interests, draft a concise day-by-day itinerary. '
    'Use one short paragraph or a few bullets per day. Keep the whole reply '
    'under 250 words.'
)


async def draft_itinerary(
    destination: str, num_days: int, interests: list[str]
) -> str:
    """Uses an LLM to draft the actual day-by-day itinerary text."""
    interests_text = ', '.join(interests) if interests else 'no particular theme'
    user_prompt = (
        f'Destination: {destination}\n'
        f'Duration: {num_days} day(s)\n'
        f'Interests: {interests_text}'
    )
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _DRAFT_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
    )
    return completion.choices[0].message.content
