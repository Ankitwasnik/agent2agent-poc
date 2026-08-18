# Agent2Agent (A2A) Protocol — PoC

A proof-of-concept implementation of the [Agent2Agent (A2A) protocol](https://a2a-protocol.org/), built with the `a2a-sdk`. Seven standalone agents, each its own server + client pair, demonstrate the protocol's communication patterns, multi-turn interaction, resilience mechanisms, and authentication model.

For full run instructions and expected output for every agent and demo, see [`poc.md`](poc.md).

## Repo structure

```
src/agent2agent/
├── flight_search/          # synchronous request/response          (port 9001)
├── itinerary_planning/      # polling                                (port 9002)
├── hotel_search/            # SSE streaming                          (port 9003)
├── visa_requirements/       # push notifications (webhook)           (port 9004)
├── restaurant_reservation/  # multi-turn interaction (INPUT_REQUIRED)(port 9005)
├── trip_booking/            # long-running + multi-turn, combined    (port 9006)
├── auth_demo/               # per-user API key auth + task isolation (port 9102)
└── resilience/              # failure-mode demos (see below)
```

Each of the first seven directories has its own `server.py` and `client.py` and runs independently — no shared orchestrator.

`resilience/` contains standalone demo scripts, each targeting a specific failure mode against one of the agents above:

- `resubscribe_demo.py` — stream drops mid-task
- `version_mismatch_demo.py` — client/server version mismatch
- `signature_demo.py` — forged/tampered agent card
- `cancel_demo.py` — task paused indefinitely, cancel + timeout policy
- `webhook_fallback_demo.py` — webhook never arrives, fallback to polling
- `retry_demo.py` — network flake, retry with backoff
- `submit_then_detach.py` / `check_later.py` — task state surviving a real session gap

## Setup

```
uv sync
```

Agents that call an LLM need an API key in `.env` at the repo root:

```
OPENAI_API_KEY=sk-...
```

## Running an agent

Each agent is a `server.py` + `client.py` pair. Start the server, keep it running, then run the client in a separate terminal:

```
uv run python -m agent2agent.<agent_name>.server
uv run python -m agent2agent.<agent_name>.client
```

e.g. `uv run python -m agent2agent.flight_search.server`.

Full instructions, expected output, and implementation notes for every agent and resilience demo are in [`poc.md`](poc.md).

## Task storage

All agents default to `InMemoryTaskStore` (fine for local dev/demos — no persistence, no eviction, single-process only). Swapping in `DatabaseTaskStore` (from `a2a-sdk[sql]`, backed by a SQLAlchemy `AsyncEngine`) is a one-line change per agent and requires no other code changes, since nothing upstream depends on the store being in-memory:

```python
# default
task_store = InMemoryTaskStore()

# production
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://user:pass@host/dbname")
task_store = DatabaseTaskStore(engine)
```
