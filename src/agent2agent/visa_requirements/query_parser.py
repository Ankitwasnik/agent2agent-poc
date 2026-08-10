"""LLM-based free-form visa/travel-requirements query parsing."""

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_SYSTEM_PROMPT = (
    'You parse free-form visa/travel-requirements requests into structured '
    "data. Extract the traveler's nationality (citizenship) and the "
    'destination country they plan to visit. If either genuinely cannot be '
    'determined from the request, list each missing piece in `missing_info` '
    'in plain language instead of guessing.'
)

_RESPONSE_SCHEMA = {
    'name': 'visa_query',
    'strict': True,
    'schema': {
        'type': 'object',
        'properties': {
            'nationality': {
                'type': ['string', 'null'],
                'description': "The traveler's citizenship/nationality, or null if unknown.",
            },
            'destination': {
                'type': ['string', 'null'],
                'description': 'The destination country being visited, or null if unknown.',
            },
            'missing_info': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "Plain-language list of what's needed before a check can run. Empty if nothing is missing.",
            },
        },
        'required': ['nationality', 'destination', 'missing_info'],
        'additionalProperties': False,
    },
}


class VisaQuery(BaseModel):
    nationality: str | None
    destination: str | None
    missing_info: list[str]


async def parse_visa_query(text: str) -> VisaQuery:
    """Uses an LLM to extract nationality/destination from free-form text."""
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
    return VisaQuery(**data)
