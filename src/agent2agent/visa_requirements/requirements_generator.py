"""LLM-based mock visa/travel-requirements drafting.

Stands in for what would, in a real system, be a slow human-in-the-loop
check against embassy/consulate data — plausible-sounding but not
authoritative, which is exactly why the agent labels it as simulated.
"""

import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

_SYSTEM_PROMPT = (
    'You are a visa requirements assistant for a travel-planning demo. '
    "Given a traveler's nationality and a destination country, write a "
    'concise, plausible summary: whether a visa is required, the maximum '
    'stay allowed without one (if applicable), and the key documents '
    'typically needed. Keep it under 120 words. This is for a prototype, so '
    "it's fine if it isn't current official guidance, but it should read as "
    'realistic.'
)


async def draft_visa_requirements(nationality: str, destination: str) -> str:
    """Uses an LLM to draft a plausible visa-requirements summary."""
    user_prompt = f'Traveler nationality: {nationality}\nDestination: {destination}'
    client = AsyncOpenAI()
    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
    )
    return completion.choices[0].message.content
