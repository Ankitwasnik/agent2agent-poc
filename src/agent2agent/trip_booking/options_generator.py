"""LLM-based flight/hotel option generation and choice interpretation.

Three separate calls, each doing one real thing: invent two distinct
flight options, map a free-form reply onto one of them, invent a hotel to
go with the finalized booking.
"""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')


class FlightOption(BaseModel):
    airline: str
    price_usd: float
    duration: str
    stops: int


_FLIGHT_SYSTEM_PROMPT = (
    'You are a flight search agent. Given a destination and a budget in '
    'US dollars, invent exactly two realistic flight options to that '
    'destination: the first direct (0 stops, pricier), the second with at '
    'least one stop (cheaper). Keep both within or reasonably close to the '
    'stated budget. Give each a realistic airline name, price, and total '
    'travel duration.'
)

_FLIGHT_RESPONSE_SCHEMA = {
    'name': 'flight_options',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'options': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'airline': {'type': 'string'},
                        'price_usd': {'type': 'number'},
                        'duration': {'type': 'string'},
                        'stops': {'type': 'integer'},
                    },
                    'required': [
                        'airline',
                        'price_usd',
                        'duration',
                        'stops',
                    ],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['options'],
        'additionalProperties': False,
    },
}


async def generate_flight_options(
    destination: str, budget_usd: float
) -> list[FlightOption]:
    """Uses an LLM to invent two distinct flight options: direct vs. with stops."""
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _FLIGHT_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': f'Destination: {destination}\nBudget: ${budget_usd:.0f}',
            },
        ],
        response_format={
            'type': 'json_schema',
            'json_schema': _FLIGHT_RESPONSE_SCHEMA,
        },
    )
    data = json.loads(completion.choices[0].message.content)
    options = [FlightOption(**opt) for opt in data['options']]
    if len(options) < 2:
        raise ValueError('Expected two flight options, got fewer.')
    return options[:2]


_CHOOSE_SYSTEM_PROMPT = (
    "You're matching a traveler's reply to one of two numbered flight "
    'options they were just shown. Given the two options and the reply, '
    'return which option number (1 or 2) they meant.'
)

_CHOOSE_RESPONSE_SCHEMA = {
    'name': 'flight_choice',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {'chosen_option_number': {'type': 'integer'}},
        'required': ['chosen_option_number'],
        'additionalProperties': False,
    },
}


async def choose_flight_option(options_text: str, reply_text: str) -> int:
    """Uses an LLM to map a free-form reply onto option 1 or 2."""
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _CHOOSE_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': f'Options:\n{options_text}\n\nTraveler reply: {reply_text}',
            },
        ],
        response_format={
            'type': 'json_schema',
            'json_schema': _CHOOSE_RESPONSE_SCHEMA,
        },
    )
    data = json.loads(completion.choices[0].message.content)
    return int(data['chosen_option_number'])


class HotelOption(BaseModel):
    hotel_name: str
    price_per_night_usd: float


_HOTEL_SYSTEM_PROMPT = (
    'You are a hotel search agent. Given a destination, suggest ONE '
    'plausible hotel: a realistic-sounding name for the destination and a '
    'believable average nightly rate in USD.'
)

_HOTEL_RESPONSE_SCHEMA = {
    'name': 'hotel_option',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'hotel_name': {'type': 'string'},
            'price_per_night_usd': {'type': 'number'},
        },
        'required': ['hotel_name', 'price_per_night_usd'],
        'additionalProperties': False,
    },
}


async def generate_hotel_option(destination: str) -> HotelOption:
    """Uses an LLM to invent one plausible hotel for the destination."""
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _HOTEL_SYSTEM_PROMPT},
            {'role': 'user', 'content': f'Destination: {destination}'},
        ],
        response_format={
            'type': 'json_schema',
            'json_schema': _HOTEL_RESPONSE_SCHEMA,
        },
    )
    data = json.loads(completion.choices[0].message.content)
    return HotelOption(**data)
