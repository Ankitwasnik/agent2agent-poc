### Flight Search Agent — synchronous request/response

Uses an LLM to parse free-form flight requests (fuzzy cities, relative dates) into a structured origin/destination/date, then looks up flights against mock data. The client sends one message and blocks until the agent has fully processed it and replies — no task ID, no polling loop, no open stream. Requires `OPENAI_API_KEY`.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.flight_search.server
   ```
   Serves on `http://localhost:9001`.

2. (Optional) confirm the agent card is being served:
   ```
   curl http://localhost:9001/.well-known/agent-card.json
   ```

3. Run the client with the default fuzzy query:
   ```
   uv run python -m agent2agent.flight_search.client
   ```
   Or with your own query — structured or free-form, both work:
   ```
   uv run python -m agent2agent.flight_search.client flights from BOS to MIA on 2026-10-05
   uv run python -m agent2agent.flight_search.client need to get from the bay area to nyc sometime next month
   ```

   Expected output:
   ```
   Query: need to get from the bay area to nyc sometime next month
   Sending request, blocking until the agent responds...

   Flights from SFO to JFK on next month:
     AA AA101  depart 08:00 -> arrive 16:25  ($342)
     UA UA245  depart 13:10 -> arrive 21:35  ($289)
   ```

   Routes with no mock data fall back to a generic flight list. If the LLM can't determine the origin, destination, or date, the agent replies asking for what's missing instead of guessing or crashing.

### Itinerary Planning Agent — polling

Uses an LLM to parse a free-form trip request (destination, number of days, interests), then a second LLM call to draft a day-by-day itinerary. Drafting takes a few seconds (plus a simulated planning delay), so the agent returns a `Task` immediately in `SUBMITTED` state and the client checks in periodically via `tasks/get` instead of blocking or holding a stream open. Requires `OPENAI_API_KEY`.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.itinerary_planning.server
   ```
   Serves on `http://localhost:9002`.

2. (Optional) confirm the agent card is being served:
   ```
   curl http://localhost:9002/.well-known/agent-card.json
   ```

3. Run the client with the default query:
   ```
   uv run python -m agent2agent.itinerary_planning.client
   ```
   Or with your own:
   ```
   uv run python -m agent2agent.itinerary_planning.client Plan a 5-day trip to Lisbon focused on history and beaches
   ```

   Expected output:
   ```
   Query: Plan a 3-day itinerary for Tokyo focused on food and temples
   Sending request...

   Task 23bd964f-fac7-4e19-bcb6-b4493e1f6bd0 submitted, status: SUBMITTED
     poll #1: status: WORKING
     poll #2: status: WORKING
     poll #3: status: WORKING
     poll #4: status: COMPLETED

   **Day 1: Explore Traditional Tokyo**
   ...
   ```

   If the LLM can't determine the destination or trip length, the task still completes, but with a clarifying message instead of an itinerary artifact — no crash, no silent guess.

### Hotel Search Agent — SSE streaming

Finds hotel options one at a time — each is its own LLM call, so each result has genuine, separate latency worth streaming as it arrives. The agent keeps one SSE connection open and sends an artifact chunk (hotel name + per-night price) as each option is found, rather than returning everything at once. Defaults to 3 options; the LLM parser picks up an explicit count from the request itself (e.g. "find me 5 hotels"), capped at 10 to keep the demo bounded. Requires `OPENAI_API_KEY`.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.hotel_search.server
   ```
   Serves on `http://localhost:9003`.

2. (Optional) confirm the agent card is being served (note `"streaming": true`):
   ```
   curl http://localhost:9003/.well-known/agent-card.json
   ```

3. Run the client with the default query:
   ```
   uv run python -m agent2agent.hotel_search.client
   ```
   Or with your own, optionally naming how many options you want:
   ```
   uv run python -m agent2agent.hotel_search.client Find 5 hotels in Paris for 2 guests, checking in 2026-10-01 and checking out 2026-10-05
   ```

   Expected output (each line prints live as the agent streams it, not all at once):
   ```
   Query: Find hotels in Tokyo for 2 guests, checking in 2026-09-10 and checking out 2026-09-14
   Opening SSE stream...

   [task]     a30c51a1-9909-44cc-84e0-582bedcfbe32 — status: SUBMITTED
   [status]   WORKING
   [status]   WORKING: Searching for hotels in Tokyo...
   [artifact]   Shinjuku Grand Hotel — $150/night
   [artifact]   Tokyo Sunshine Inn — $120/night
   [artifact]   Tokyo Urban Lodge — $130/night
   [status]   COMPLETED
   ```

   If the LLM can't determine the destination, check-in, or check-out date, the task still completes, but with a clarifying message instead of hotel results.

### Visa/Travel-Requirements Agent — push notifications (webhook)

Checks visa/entry requirements for a nationality + destination — standing in for a slow, human-in-the-loop process (an embassy/document review). Too long to poll for or hold a stream open across, so the client registers a webhook URL when it sends the request, gets an immediate acknowledgement, and then does nothing but wait: the agent's server calls back to the client's own tiny local HTTP endpoint as the task progresses. Requires `OPENAI_API_KEY`. The client runs its own webhook listener on port 8004, so make sure that port is free.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.visa_requirements.server
   ```
   Serves on `http://localhost:9004`.

2. (Optional) confirm the agent card is being served (note `"pushNotifications": true`):
   ```
   curl http://localhost:9004/.well-known/agent-card.json
   ```

3. Run the client with the default query:
   ```
   uv run python -m agent2agent.visa_requirements.client
   ```
   Or with your own:
   ```
   uv run python -m agent2agent.visa_requirements.client Do I need a visa? I am a UK citizen traveling to Brazil.
   ```

   Expected output:
   ```
   Query: Do I need a visa? I am a US citizen traveling to Vietnam.
   Registering webhook: http://localhost:8004/webhook
   Sending request...

   [webhook] task — status: SUBMITTED
   Task e4a976ff-3e42-494e-be06-3071bd7fb9a3 submitted, status: SUBMITTED
   Waiting for push notifications (no polling loop, no open stream held by this client)...

   [webhook] status: WORKING
   [webhook] status: WORKING: Checking visa requirements for a US citizen traveling to Vietnam...
   [webhook] artifact:
   As a US citizen traveling to Vietnam, you will need a visa to enter the country...

   (Simulated for this demo — verify with official sources before travel.)
   [webhook] status: COMPLETED
   ```

   Every line prefixed `[webhook]` arrived via the agent POSTing to the client's local listener, not through the original request or any polling call. If the LLM can't determine the nationality or destination, the task still completes — pushed the same way — with a clarifying message instead of a requirements summary.

### Restaurant Reservation Agent — multi-turn interaction (`TASK_STATE_INPUT_REQUIRED`)

A fifth agent, added later to cover a pattern the original four don't: a task that can't be resolved in one call. Every other agent above either has everything it needs or gives up in one final, terminal message. This one doesn't give up — if required details are still missing after a turn, the task pauses in `INPUT_REQUIRED` state and asks, instead of completing. The client's next message, sent with the *same* task ID and context ID, resumes the *same* conversation: the executor re-parses the entire conversation so far (not just the latest message) to decide what's still missing. Requires `OPENAI_API_KEY`.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.restaurant_reservation.server
   ```
   Serves on `http://localhost:9005`.

2. (Optional) confirm the agent card is being served:
   ```
   curl http://localhost:9005/.well-known/agent-card.json
   ```

3. Run the client:
   ```
   uv run python -m agent2agent.restaurant_reservation.client
   ```

   The client runs a short, scripted two-turn conversation: a deliberately incomplete opener, then a follow-up filling in whatever the agent asked for. Each turn is one blocking call, exactly like the Flight Search client — the difference is entirely in what the task itself does with it.

   Expected output:
   ```
   Turn 1 (user):  I'd like to book a table at Le Jardin for tomorrow evening.
   Turn 1 (agent, INPUT_REQUIRED): How many people will be in your party?

   Turn 2 (user):  7:30 PM, for 4 people please.
   Turn 2 (agent, COMPLETED):
   Reservation confirmed:
     Restaurant : Le Jardin
     Date       : tomorrow
     Time       : 7:30 PM
     Party size : 4
   ```

   Turn 1 only asked for what was actually still missing (the LLM judged "tomorrow evening" specific enough for date/time on the first pass) — turn 2's answer is merged with turn 1's context, not treated as a fresh request, which is the whole point: the task never restarted, it picked up exactly where it left off.

### Trip Booking Agent — long-running work with a mid-task pause (`TASK_STATE_INPUT_REQUIRED` + polling)

A sixth agent, combining two patterns the PoC only showed separately until now: real long-running work (WORKING for several real seconds, pollable — like Itinerary Planning) and a mid-task pause for human input (`INPUT_REQUIRED` — like Restaurant Reservation). The agent searches for flights (genuinely slow), pauses to ask which option to book, then resumes and does *more* real work (booking a hotel, finalizing) before completing. Which stage a given call is resuming into is derived from the task itself — if a `flight-options` artifact already exists on it, that call is answering the pause, not starting fresh; no separate state variable is needed. Requires `OPENAI_API_KEY`.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.trip_booking.server
   ```
   Serves on `http://localhost:9006`.

2. (Optional) confirm the agent card is being served:
   ```
   curl http://localhost:9006/.well-known/agent-card.json
   ```

3. Run the client:
   ```
   uv run python -m agent2agent.trip_booking.client
   ```

   The client submits the trip request, polls while the agent searches for flights, answers the flight-choice question with a follow-up message using the same task ID, then polls again while the agent finalizes the booking — no streaming, no held-open connection, just periodic `tasks/get` checks on both sides of the pause.

   Expected output:
   ```
   Turn 1 (user):  Book me a trip to Tokyo. My budget is $2000.
   Task 410c0d68-a546-427c-a9a6-cf461ca502f5 submitted, status: SUBMITTED
     poll: WORKING — Searching flights to Tokyo...
     poll: WORKING — Searching flights to Tokyo...
     poll: WORKING — Searching flights to Tokyo...
     poll: INPUT_REQUIRED — I found two flight options:
     1. Japan Airlines — $1800 — 13h 45m (direct)
     2. Air Canada — $1200 — 18h 30m (1 stop(s))

   Which one would you like — 1 or 2?

   Turn 1 (agent, INPUT_REQUIRED): I found two flight options:
     1. Japan Airlines — $1800 — 13h 45m (direct)
     2. Air Canada — $1200 — 18h 30m (1 stop(s))

   Which one would you like — 1 or 2?

   Turn 2 (user):  I'll take the cheaper one with the stopover.
   Task resumed, status: WORKING
     poll: WORKING
     poll: WORKING — Finalizing your booking...
     poll: WORKING — Finalizing your booking...
     poll: COMPLETED

   Booking confirmed!
     Flight : 2. Air Canada — $1200 — 18h 30m (1 stop(s))
     Hotel  : Shinjuku Grand Hotel — $150/night
   ```

   Both flight options are LLM-generated, not fixtures (one direct/pricier, one with-stops/cheaper) — the follow-up reply ("the cheaper one with the stopover") is matched onto the correct option by a small LLM call, not keyword matching. By the time the task completes it carries two artifacts — the flight options from the first phase, and the confirmation from the second — the client filters to show only the latter.

### Auth Demo Agent — authentication & authorization

A seventh agent, added to close a gap the rest of the PoC only analyzed from the SDK's source: none of the other six agents implement authentication at all. This one requires a per-user API key and proves two things at once — that the auth check is real (not just declared on the card), and that per-user task isolation falls out of `InMemoryTaskStore`'s owner-scoping automatically once a real authenticated user exists. No `OPENAI_API_KEY` needed; nothing here calls an LLM.

1. Start the server (keep running in its own terminal):
   ```
   uv run python -m agent2agent.auth_demo.server
   ```
   Serves on `http://localhost:9102`.

2. Run the client:
   ```
   uv run python -m agent2agent.auth_demo.client
   ```

   The client makes four calls as four different callers — no key, a wrong key, then two valid, distinct users (Alice and Bob) — never setting an auth header by hand: `AuthInterceptor` reads the fetched card's declared `apiKeyAuth` scheme and attaches the right credential on its own.

   Expected output:
   ```
   Agent requires: ['apiKeyAuth'] (fetched anonymously — the card itself needs no key)

   --- Anonymous (no API key) ---
     send_message REJECTED: HTTP Error 401: Client error '401 Unauthorized' for url 'http://localhost:9102/'

   --- Invalid API key ---
     send_message REJECTED: HTTP Error 401: Client error '401 Unauthorized' for url 'http://localhost:9102/'

   --- Alice (valid key) ---
     send_message -> Hello, alice! You said: 'hello'
     tasks/list  -> 1 task(s) visible to this caller

   --- Bob (valid key) ---
     send_message -> Hello, bob! You said: 'hello'
     tasks/list  -> 1 task(s) visible to this caller
   ```

   The agent-card route itself stays open to anonymous requests on purpose — the "single-fetch discovery" model (see blog.md's "Core Concepts" section) only holds if a client can fetch the card *before* it has any credentials to present. The isolation proof is in the last pair: Bob's `tasks/list` shows exactly one task — his own — not two. If `InMemoryTaskStore`'s owner-scoping weren't keying storage by authenticated user, Bob would see Alice's task sitting right there next to his. Full write-up of what's actually enforced vs. merely declared is in blog.md's "Authentication and Authorization" section.

## Failure-Mode Demos

Standalone scripts under `src/agent2agent/resilience/` covering the failure modes discussed in blog.md's "Designing for Failure" section: a stream dropping mid-task, a webhook never arriving, a forged/tampered agent card, a version mismatch, a task stuck indefinitely, and a network flake. **No agent server code changed for any of these** — 6 of 7 demos are pure new client scripts reusing one of the four agents above exactly as already built, because the failure-handling machinery (version checks, cancel, push-notification best-effort delivery, resubscribe/snapshot replay) already lives in the a2a-sdk's request handler, not in anything we wrote. The one exception is `signature_demo.py`, which stands up its own tiny dedicated card-only server (no executor, no task handling) since signing needs a card to sign. **Start the relevant agent server(s) from the sections above first** (all four running at once is simplest). None of these need `OPENAI_API_KEY` directly, but the agent they call against might. Signature verification also needed two new dependencies: `a2a-sdk[signing]` (pulls in PyJWT) and `cryptography` (for RSA key generation, since verification is asymmetric — see below).

| Demo | Failure mode | Agent used |
|---|---|---|
| `resubscribe_demo.py` | Stream drops mid-task → resubscribe replays full snapshot | Hotel Search (9003) |
| `version_mismatch_demo.py` | Version mismatch → loud `VersionNotSupportedError` | Flight Search (9001) |
| `signature_demo.py` | Forged/tampered agent card → signature verification | its own mini card server (9101) |
| `cancel_demo.py` | Task paused indefinitely → `tasks/cancel`, `TaskNotCancelableError` | Itinerary Planning (9002) |
| `webhook_fallback_demo.py` | Webhook never arrives → best-effort by design | Visa Requirements (9004) |
| `retry_demo.py` | Network flake → client retry with backoff | Flight Search (9001) |
| `submit_then_detach.py` + `check_later.py` | Task state survives across a real process/session gap | Itinerary Planning (9002) |

### Stream drops mid-task → resubscribe (`resubscribe_demo.py`)

Opens an SSE stream to the Hotel Search agent, force-closes the connection after a few events (`stream.aclose()` — a real teardown of the underlying HTTP connection, not just breaking a loop), waits 2s while the agent keeps working unaware anyone left, then calls `tasks/subscribe` to reattach to the same task.

**What was built:** only a new client script — the Hotel Search agent (`server.py`, `agent_executor.py`, port 9003) is untouched. `client.send_message(request)` returns an async generator; the script consumes a few events off it, then calls `.aclose()` directly on that generator instead of just `break`-ing out of the loop, so the `GeneratorExit` propagates all the way down through the SDK's chained async generators to the innermost `async with _SSEEventSource(...)` block and genuinely closes the HTTP connection (verified this in the transport source before relying on it). After the gap, `client.subscribe(SubscribeToTaskRequest(id=task_id))` calls the server's `on_subscribe_to_task`, which yields the full current `Task` snapshot first (`include_initial_task=True`) before resuming live events — that's the mechanism, not anything this script does. The only original code here is the try/except around `InvalidParamsError` that falls back to `tasks/get` if the task already finished and got evicted from active tracking during the gap (see "How Long Does a Task Actually Stick Around?" below).

```
uv run python -m agent2agent.resilience.resubscribe_demo
```

Expected: the resubscribe's first event is the **current full Task snapshot** — including any artifact found while disconnected — proving nothing was lost, before live events resume:

```
[live]                      task ... — status: SUBMITTED, artifacts so far: 0
[live]                      status: WORKING
[live]                      status: WORKING: Searching for hotels in Tokyo...

--- Simulating a dropped connection (closing the stream early) ---
--- Disconnected for 2s. The agent keeps working in the background, unaware the client left. ---

--- Resubscribing to task ... ---
[resubscribe: full snapshot] task ... — status: WORKING, artifacts so far: 1
[resubscribe: live]          artifact:   Tokyo Urban Suites — $150/night
[resubscribe: live]          artifact:   Samurai Inn Tokyo — $150/night
[resubscribe: live]          status: COMPLETED
```

If `GAP_SECONDS` is raised enough that the task finishes (and gets cleaned up from active tracking) before the resubscribe call, `tasks/subscribe` raises `InvalidParamsError: Task ... is in terminal state: ...` instead — there's nothing left to subscribe to. The demo catches exactly this and falls back to a plain `tasks/get` call, which always works since it reads the persisted task store directly rather than active-task tracking. Worth trying both: it's the same lesson the other rows teach — know your fallback.

### Version mismatch (`version_mismatch_demo.py`)

Sends the same request to the Flight Search agent three times with different `A2A-Version` headers: matching (1.0), a newer minor version (1.7, still compatible since only the major version is checked), and a mismatched major version (2.0).

**What was built:** only a new client script — the Flight Search agent (port 9001) needed zero changes, since every JSON-RPC method the SDK generates via `create_jsonrpc_routes` is already wrapped in `@validate_version(PROTOCOL_VERSION_1_0)` (confirmed by reading `jsonrpc_dispatcher.py` directly, not assumed). The script builds three separate `httpx.AsyncClient` instances, each with a different `A2A-Version` header pre-set before constructing `ClientConfig` — `ClientFactory` only `setdefault`s that header, so a value set ahead of time sticks. `VersionNotSupportedError` on the mismatched call is the exact exception class reconstructed client-side from the JSON-RPC error code (`-32009`), so `except VersionNotSupportedError` catches it directly; no custom error handling needed.

```
uv run python -m agent2agent.resilience.version_mismatch_demo
```

Expected: the first two succeed normally; the third raises an explicit `VersionNotSupportedError` instead of the server silently misreading the request:

```
--- Mismatched major version (2.0) (A2A-Version: 2.0) ---
VersionNotSupportedError (explicit, not silent): A2A version '2.0' is not supported by this handler. Expected version '1.0'.
```

### Forged/tampered agent card (`signature_demo.py`)

Fully self-contained — signs its own demo AgentCard with a real asymmetric key pair (RS256) and serves it from a tiny dedicated server on port 9101, no other agent needed.

**What was built:** the only new *server* in the whole resilience suite — a minimal Starlette app with just `create_agent_card_routes(signed_card)` mounted, no `RequestHandler`, no `AgentExecutor`, no task store, because this demo never actually calls the agent for work, only fetches and verifies its card. Signing/verification themselves are the SDK's `a2a.utils.signing` module (`create_agent_card_signer`, `create_signature_verifier`) — new dependencies `a2a-sdk[signing]` (PyJWT) and `cryptography` (RSA key generation) were added for this. An RSA-2048 key pair is generated once at startup: the **private** key signs the card and never leaves that function; the client's `key_provider` callback only ever hands back the **public** key — mirroring how a real client would trust a key it obtained out-of-band (a published JWK Set, a key pinned during onboarding), never one supplied by the card being verified. `A2ACardResolver.get_agent_card(signature_verifier=...)` does the real HTTP fetch + verify in one call.

Two rejection scenarios, not just one:
- **Tampering** — the fetched card is deep-copied (`AgentCard().CopyFrom(card)`), one field is mutated, and the *same* verifier is called again directly on the mutated copy (no second HTTP round-trip needed): the signature no longer matches the altered content.
- **Forgery** — a second, independent RSA key pair stands in for an attacker who fabricates a lookalike card (same name, malicious description) and signs it with *their own* private key, reusing the same `kid` header (that's public information, trivial to copy). The client's `key_provider` doesn't look anything up from the card itself — it always returns the one public key it already trusts for that `kid` — so the attacker's signature fails to verify against it, exactly as it would for any key the client didn't already trust.

```
uv run python -m agent2agent.resilience.signature_demo
```

Expected: the genuine card verifies successfully; both attacks are rejected with `InvalidSignaturesError` — the client's own acceptance rule catching what the protocol itself doesn't force it to check:

```
--- 1. Fetching the genuine, signed card ---
Fetched "Signed Demo Agent" — signature verified OK (RS256, asymmetric — no shared secret involved).

--- 2. Simulating tampering: mutating a field after the fact ---
Rejected as expected: No valid signature found — the payload no longer matches what was signed.

--- 3. Simulating forgery: an attacker signs a lookalike card with THEIR OWN key ---
Rejected as expected: No valid signature found — validly formed and self-consistent, but not signed by a key this client trusts.
```

### Task paused indefinitely → cancel + timeout policy (`cancel_demo.py`)

Submits an itinerary-planning task with a **client-side timeout budget (3s)** deliberately shorter than the agent's real work time, polling until the budget is exceeded, then cancels — followed by a second cancel attempt on the now-terminal task.

**What was built:** only a new client script — the Itinerary Planning agent (`agent_executor.py`, port 9002) already implements `cancel()` properly (it was written that way when the agent was first built above, even though nothing exercised it until now), and `tasks/cancel`/`TaskNotCancelableError` are handled entirely by `DefaultRequestHandler`'s built-in `on_cancel_task`. The "timeout policy" is just a plain `while` loop comparing elapsed polling time against `CLIENT_TIMEOUT_BUDGET_SECONDS`, then calling `client.cancel_task(CancelTaskRequest(id=task.id))` once the budget is blown. The second call, on the now-`CANCELED` task, is what actually triggers `TaskNotCancelableError` — confirmed by tracing it back to `ActiveTask.start()` raising `InvalidParamsError` for a task already in a terminal state, which `on_cancel_task` catches and re-raises as `TaskNotCancelableError` specifically.

```
uv run python -m agent2agent.resilience.cancel_demo
```

Expected:

```
--- Exceeded client timeout budget of 3s — canceling task ... ---
Task status after cancel: CANCELED

--- Attempting to cancel the same task again (it is already terminal) ---
TaskNotCancelableError (explicit, not a silent no-op): Task cannot be canceled
```

### Webhook never arrives → fallback to polling (`webhook_fallback_demo.py`)

Registers a push-notification webhook pointing at a port nothing is listening on, so every delivery attempt genuinely fails server-side (visible in the agent's own logs as a warning, never surfaced to the client). After a timeout, the client gives up waiting and falls back to plain `tasks/get` polling.

**What was built:** only a new client script — the Visa Requirements agent (port 9004) is unmodified; its `BasePushNotificationSender` already POSTs best-effort and only logs a warning on failure (`Some push notifications failed to send for task_id=...`), which is exactly the behavior this demo needed and confirmed directly in the server's own log output rather than assuming it. The script sets `ClientConfig(push_notification_config=TaskPushNotificationConfig(url=UNREACHABLE_WEBHOOK_URL))` pointing at a port with nothing bound to it, waits `WEBHOOK_WAIT_TIMEOUT_SECONDS` on a plain `asyncio.sleep` (there's no event to actually wait on, since no webhook is listening), then switches to the exact same `tasks/get` polling loop pattern used by the Itinerary Planning client above.

```
uv run python -m agent2agent.resilience.webhook_fallback_demo
```

Expected: a 5s wait for a push that never comes, then a normal polling loop to completion — same visa-requirements result as the push-based demo above, just delivered differently.

### Network flake → retry with backoff (`retry_demo.py`)

Wraps the httpx transport so the first 2 requests to the Flight Search agent fail with a simulated connection error, then succeed. A2A itself gives you nothing for this case — it's a plain client-side retry loop with exponential backoff.

**What was built:** only a new client script — the Flight Search agent (port 9001) is unmodified and, notably, never even needs to know anything went wrong, since the simulated failure happens entirely on the client's own httpx transport before any bytes reach the network. A new `FlakyTransport(httpx.AsyncBaseTransport)` class wraps a real `httpx.AsyncHTTPTransport` and raises `httpx.ConnectError` for the first `FAIL_FIRST_N_ATTEMPTS` calls, then delegates normally. Card resolution uses a separate, non-flaky `httpx.AsyncClient` so only the actual RPC call is affected. Traced how the SDK handles this: `httpx.RequestError` gets caught inside `handle_http_exceptions` and re-raised as `A2AClientError` (not left as a raw `httpx.ConnectError`), so `send_with_retry()` catches `A2AClientError` specifically, not the httpx exception directly — getting this wrong would have made the retry loop silently do nothing.

```
uv run python -m agent2agent.resilience.retry_demo
```

Expected:

```
Attempt 1 failed (Network communication error: simulated network flake (attempt 1)) — retrying in 0.5s...
Attempt 2 failed (Network communication error: simulated network flake (attempt 2)) — retrying in 1.0s...

Succeeded after retrying:
Flights from SFO to JFK on 2026-09-01:
  ...
```

### Task state survives a real session gap (`submit_then_detach.py` + `check_later.py`)

Two genuinely separate process invocations sharing nothing but a task ID — proof that task state lives on the server, not in any one client's memory.

**What was built:** two small new client scripts, no server changes — the Itinerary Planning agent (port 9002) is exactly as built above. `submit_then_detach.py` sends with `polling=True` for a fast ack, prints the task_id, and returns — the `asyncio.run(main())` call ends, the Python interpreter exits, every in-memory object (httpx client, task reference, everything) is gone. `check_later.py` is invoked afterward as a completely unrelated `python -m` invocation, with only the task_id string (typed or pasted) connecting it to the first run; it calls `client.get_task(GetTaskRequest(id=task_id))` cold and, if not yet terminal, polls the same way the itinerary client above does. Nothing links the two processes except that task_id and the agent server that outlived both of them.

Run the first, wait however long you like (seconds or much longer), then run the second in a new terminal with the printed task ID:

```
uv run python -m agent2agent.resilience.submit_then_detach
# ... wait a bit, then in a new terminal: ...
uv run python -m agent2agent.resilience.check_later <task_id>
```

`check_later.py` reattaches with a fresh `tasks/get` call and, if the task isn't done yet, keeps polling — arriving at the correct final state regardless of how long the gap was.

## How Long Does a Task Actually Stick Around?

`resubscribe_demo.py` surfaces a subtlety worth calling out on its own: there are two separate layers of "task state" in the SDK, with very different lifetimes.

**The task record itself — `TaskStore`.** Every agent in this repo uses `InMemoryTaskStore` (from `a2a.server.tasks`): a plain Python dict living in the server process's memory, keyed by owner → task_id. This is what `tasks/get` reads from. There is no TTL, no expiration, no automatic cleanup — a task created an hour ago is still sitting in that dict, retrievable via `tasks/get`, for as long as the server process keeps running. It only disappears if the process restarts (the dict is gone — memory, not disk) or something explicitly calls `task_store.delete(...)` (none of these agents ever do). For real persistence across restarts, the SDK also ships `DatabaseTaskStore` (`a2a-sdk[sql]`) — same `TaskStore` interface, backed by a real database instead of a dict, so tasks survive a server restart. Swapping one for the other is a one-line change in each agent's `server.py` (`task_store=InMemoryTaskStore()` → `task_store=DatabaseTaskStore(...)`); everything else (executors, clients, routes) is unaffected because they only ever talk to the `TaskStore` interface.

**The live tracking layer — `ActiveTaskRegistry`.** This is separate, shorter-lived bookkeeping for the background asyncio producer/consumer pair that drives a task while it's running or being watched. It gets cleaned up automatically the moment a task reaches a terminal state (`COMPLETED`/`FAILED`/etc.) **and** has zero subscribers. That's exactly what `resubscribe_demo.py` can hit with a large enough `GAP_SECONDS`: the task finishes, nobody's subscribed (the client disconnected), the `ActiveTask` gets evicted — so `tasks/subscribe` raises `InvalidParamsError` (nothing left to subscribe to), while `tasks/get` still succeeds, because it never depended on active tracking in the first place.

In short: subscribe/stream tracking is ephemeral and cleaned up fast; the task record itself is effectively permanent for this demo (`InMemoryTaskStore`, no eviction) until the server restarts — and would need `DatabaseTaskStore` to survive that too.
