# Agent2Agent protocol 

## 1. What is Agent2Agent Protocol?
Agent2Agent(A2A) protocol is an open standard for communication between AI agents. In recent years, we have seen a lot of growth in agentic applications. As this matures, it makes more sense to use agents developed by other people or companies rather than we reinventing the wheels ourselves.
In the early era of the computers, people used computers locally, running programs on isolated machines that had no real way to talk to one another. Then came internet and suddenly computers could talk to each other over standard protocols like TCP/IP and HTTP. This one change unlocked everything we take for granted - email, web, APIs, cloud computing.  We are at a similar point with AI agents today. Right now, most agentic systems work in their own silos, unable to collaborate with agents built on different frameworks or vendors. A2A is trying to be that protocol which will allows agents to find other agents, work together regardless of the underlying tools they run on - the HTTP moment for the agents.   
The core design principle worth calling out explicitly: Agents can securely exchange information to achieve a user's goal without needing access to each other's internal state, memory, or tools. An agent simply publishes what it can do, and other agents interact with it purely through messages, treating it as a black box. This is deliberate. It means a finance agent built in-house doesn't need to know whether a travel-booking agent it's talking to is running on LangChain, a custom stack, or something a vendor ships as a black box behind an API. 
A2A was originally developed by Google and donated to the Linux Foundation.  

## 2. Why Do We Need A2A? When Not to Use It
2a. Why a delegated call isn't just a tool call
The first time you look at an A2A message, it's tempting to say, "isn't this just a REST call with extra steps?" It's a fair question, and honestly a healthy one to ask before adopting any new protocol. But a tool call and a delegated A2A call are solving different problems.
When you call a tool like a weather API or a database query you already know what you will get back. You know what the output will look like because you wrote the code or someone gave you the documentation. The interaction is always the same: you put in the input you get the same output. A tool does not make decisions it just does what it is told.
An agent is different. When you use A2A to delegate a task to another agent you are not just calling a function. You are giving a goal to something that can think, plan and use tools to get the job done. This can take minutes and the agent might even ask you questions along the way. You do not know how the agent will do the task and you do not need to know. A2A is designed to handle this uncertainty. It has features for long tasks, updates and checking the status.
Could you build a custom API to do all this? Yes, you could. Then you would have to maintain special code for every new agent you want to work with. That code would break every time the other team changes how their agent works. A2A is a protocol that everyone can use so you only have to write the integration code.
2b. When A2A actually pays off
A2A is useful in a situation: when you need to work with an agent that you do not control and you want to be able to change your implementation without affecting the other agent.
This is important in environments where multiple teams and vendors are working together. For example, a company might use a customer-support agent from one vendor, a fraud-detection agent from another vendor and an internal scheduling agent. All these agents need to be able to work. A2A is also useful when you are building a platform and you want other teams to be able to plug in their agents without you having to write special code for each one.
If you think you will need to add agents or swap vendors in the future it is worth using A2A. The extra work you put in at the beginning will pay off in the long run.
2c. When not to use it
You do not need to use A2A for everything. If you are building two agents that will only talk to each other and you are in control of both agents a custom internal API might be simpler and faster to build. You do not need A2A if you are not solving an interoperability problem.
Also, if the other side of the interaction is a simple function like getting the current stock price or validating a zip code you do not need A2A. That is just a tool call, not a delegation. Using A2A in this case would just add work.
If latency is a big concern for you, you should know that A2A can add a bit of overhead. 

## 3. Features (Core Concepts)
Underneath everything A2As data model comes down to five concepts: Task, Message, Agent Card, Part and Artifact. 

- A Task is the unit of work being delegated. 
- A Message is a turn in the conversation around that task. 
- A Part is a chunk of content inside a message or artifact - Text, a file, data. 
- Artifact is the actual output the task produces. 
- The Agent Card is how an agent introduces itself.
Whats worth noting isn't the list itself. It's that these are defined once in protobuf and then bound to three interchangeable transports (JSON-RPC, gRPC and REST/HTTP+JSON). That's a choice: it means two agents don't need to agree on a transport to be A2A-compliant only on the shape of the data flowing over it. One team can run gRPC internally for performance another can expose REST for easier debugging and they still speak the same protocol underneath.
Think of the Agent Card as an agent's digital business card. It's a JSON document an agent hands out for discovery and initial setup, packed with everything a client needs to decide two things: is this agent right for the task, and if so, how do I actually talk to it? That includes the agent's identity, where to reach it (its service endpoint), what A2A capabilities it supports, what authentication it expects, and the specific list of skills it offers. 
This single-fetch model is what makes discovery cheap. There's no negotiation dance, no back-and-forth just to figure out if an agent can do what you need. You read the card once. You know.


### Four ways of communication


1. **Synchronous (request/response).** One call, one blocking wait, one final answer — no task ID, nothing to check back on later. Fits work fast and deterministic enough that waiting for it is simply fine. The agent signals this itself by enqueueing a single `Message` rather than a `Task`.
2. **Polling.** The agent hands back a `Task` immediately (typically `SUBMITTED`), and the client periodically calls `tasks/get` until it reaches a terminal state. Fits work that takes a noticeable amount of time but doesn't need live progress — a "check back in a bit" relationship.
3. **Server-Sent Events (streaming).** The client holds one HTTP connection open and receives `TaskStatusUpdateEvent`/`TaskArtifactUpdateEvent` updates live as the agent produces them. Fits work with genuine incremental progress worth watching happen, rather than just waiting for a final result.
4. **Push notifications (webhook).** The client registers a callback URL up front, gets an immediate acknowledgment, and does nothing else — the agent's server POSTs updates to that URL as the task progresses. Fits long-running, human-in-the-loop-shaped work where the client shouldn't have to stay connected or keep asking. Delivery is explicitly best-effort (no retry, no guarantee), which is exactly why Section 8 insists a resilient client always pairs this with a timeout-and-fallback-to-polling.

This PoC builds one agent per pattern — Flight Search (synchronous), Itinerary Planning (polling), Hotel Search (streaming), Visa/Travel-Requirements (push) — with full run instructions in `poc.md`.


## 4. PoC — Designing a System with A2A

**The PoC idea:** a "Trip Planner" — not one agent that happens to support all four communication patterns, but **four independent agents, one per pattern**, each its own standalone server + client pair, its own port, no shared orchestrator. Isolating each pattern in its own agent keeps every one legible on its own, rather than burying the distinction inside branching logic in a single agent.

- **Flight Search** (synchronous) — look up flights for a destination/date. Fast and deterministic enough that a blocking call is simply the right fit; no task ID needed at all.
- **Itinerary Planning** (polling) — draft a day-by-day plan. Drafting genuinely takes a few real seconds (an LLM call plus a simulated planning delay), long enough to be worth a `Task`, not so long that live updates matter — a "check back in a bit" relationship.
- **Hotel Search** (SSE streaming) — find hotel options one at a time. Each result is its own real unit of work with its own latency, worth watching arrive live rather than waiting silently for a final batch.
- **Visa/Travel-Requirements** (push notifications) — check visa requirements for a nationality/destination. This is the agent that actually satisfies 4a's "long-running + human-in-the-loop" criterion directly: it stands in for a slow embassy/document review, the kind of task where a client shouldn't have to stay connected or keep asking at all.

Each agent uses an LLM for real query understanding and/or result generation (not canned responses) so the PoC demonstrates actual agent behavior, not just protocol plumbing wired to fixtures. Full build and run instructions in Section 6 / `poc.md`; what came out of building it is in Section 7.


## 6. Running the PoC

The PoC is a "Trip Planner" scenario: four independent agents, each exposing one of the four ways a client can talk to an A2A agent. Each agent has its own standalone server + client under `src/agent2agent/`, its own port, and no shared orchestrator — run each pair on its own.

Setup (once):
```
uv sync
```

Some agents call an LLM and need an API key in `.env` at the repo root:
```
OPENAI_API_KEY=sk-...
```

Full run instructions, expected output, and implementation notes for each of the four agents and the seven failure-mode demos live in **`poc.md`**. What follows here is what actually came out of building and testing all of it — the findings, not the how-to.

## 7. Findings From Building the PoC

### The four communication patterns really are just transport choices, not different agents

The most concrete confirmation of Section 1's "black box" claim: the Itinerary Planning agent (polling) and the Visa/Travel-Requirements agent (push notifications) run **the exact same shape of executor code** — enqueue a `Task`, call `TaskUpdater.start_work()`, do the real work, `add_artifact()`, `complete()`. Nothing in `agent_executor.py` knows or cares whether the client is going to poll `tasks/get` or sit back and wait for a webhook. That decision is made entirely on the server's wiring (`server.py` — whether a `push_config_store`/`push_sender` are attached to the `DefaultRequestHandler`) and the client's config (`ClientConfig(polling=True)` vs. attaching a `push_notification_config`). The agent genuinely doesn't need to know which one it's going to get.

The one real branch point in agent code is **Message vs. Task**: enqueueing a single `Message` (Flight Search) tells the framework "this is a one-shot, immediate answer" — no task ID, no polling, no push config even possible. Enqueueing a `Task` opts into the entire long-running lifecycle (status updates, cancellation, resumability, push eligibility) at once. That's the one structural decision an agent author actually makes; everything downstream of it (sync/polling/streaming/push) is a client-and-transport-level choice, not something the agent's own logic branches on.

### The Agent Card is fetched once, then never travels with a request again

Confirmed this by reading the client code path rather than assuming it: `A2ACardResolver.get_agent_card()` does one GET to `/.well-known/agent-card.json`, and the resulting `AgentCard` is cached inside the `Client` object (`self._card`) for its whole lifetime. Every later call — `send_message`, `get_task`, `cancel_task`, `subscribe` — only sends its own method-specific JSON-RPC params; the card itself never re-appears on the wire. The only thing that *does* travel with every request is a small `A2A-Version` header. This is exactly what makes the "single-fetch discovery" pitch in Section 3 literally true, not just a nice description.

### Six of the seven failure-mode demos needed zero agent changes

Version mismatch checking, `tasks/cancel`/`TaskNotCancelableError`, resubscribe-with-snapshot-replay, and best-effort push delivery are **already implemented in the a2a-sdk's request handler** — none of it is something an agent author has to write. Every failure-mode demo except `signature_demo.py` reused one of the four agents completely unmodified; only signature verification needed a dedicated (executor-less) mini server, because the whole point of that demo was to control both sides of a signing keypair. In other words: most of what the README's original failure-modes table (Section 4d) worried about turned out to be the framework's job, not the application's — the actual application-level work was almost entirely on the *client* side (timeout policies, retry loops, fallback-to-polling), which matches the table's own "what you still have to build" column.

### A task has two lifetimes, and mixing them up is the one real gotcha we hit

Testing `resubscribe_demo.py` with a longer disconnect gap surfaced a genuine two-tier lifecycle: the task *record* (`InMemoryTaskStore`, a plain dict with no expiry, effectively permanent until the server restarts) and the *live tracking* of it (`ActiveTaskRegistry`, torn down the moment a task is terminal and has no subscribers). `tasks/subscribe` depends on the second and fails once it's gone; `tasks/get` depends only on the first and always works. A client that only knows how to resubscribe, without a `tasks/get` fallback, will break on exactly this timing — which is precisely why the resilience demo needed both.

### Signature verification only means something with asymmetric keys and your own trust store

The first pass at `signature_demo.py` used a shared HS256 secret, which technically worked but quietly assumed the client already had a side-channel to the agent — fine for a closed fleet, useless for verifying a random third-party agent. Switching to RS256 (private key signs, public key verifies) and adding a genuine forgery scenario (an attacker with their *own* keypair, signing a lookalike card) made the actual point land: `key_provider` is where the client's own trust decision lives, wholly separate from anything the card claims about itself. A forged card can copy any field it wants, including the `kid` — what it can never do is produce a signature that verifies under a public key it doesn't control. That's the entire mechanism, and the protocol only supplies it; deciding which keys to trust is left to the client, exactly as the original plan's "your own acceptance rule" line said it would be.

### Network flakiness and webhook delivery are explicitly not the protocol's problem

Both `retry_demo.py` and `webhook_fallback_demo.py` confirmed something the original plan's table already stated but which is worth having actually seen: `BasePushNotificationSender` logs a warning and moves on when a webhook POST fails — it does not retry, and that failure never reaches the client. A plain `httpx.ConnectError` is never softened into anything friendlier by the SDK either. Both are squarely "bring your own resilience" by design, not oversights.

## 8. What a Resilient Agent Client Should Actually Do

A client only earns the label "resilient" if it goes in assuming every one of these will eventually happen: connections drop, webhooks never arrive, the agent takes longer than expected, its card gets tampered with in transit, and the network just flakes out for no reason. Section 7 covers what testing each of those individually showed us; here's what it adds up to as an actual design.

**1. Verify identity before you trust capability.** Don't fetch a card and act on it — fetch it, verify the signature against a public key *you already decided to trust*, and only then read `capabilities`/`supported_interfaces` to decide how to talk to the agent. Being well-formed JSON doesn't make a card self-authenticating. → `signature_demo.py`

**2. Know what you got back before you assume you can watch it.** A `Message` response is final — no task ID, nothing to poll, stream, or cancel. Only a `Task` response gives you an ID worth holding onto. Branch on which one you got; don't assume every reply is pollable. → Flight Search (Message) vs. the other three agents (Task)

**3. Persist the task ID the moment you have it — it's the only thing guaranteed to survive a crash.** Everything else — the httpx client, in-memory state, the process itself — can disappear without losing anything, as long as the task ID was written down somewhere durable. A client that only keeps task state in memory has, by construction, no resilience story for its own crashes. → `submit_then_detach.py` + `check_later.py`

**4. Layer your "watch this task" strategy: stream → resubscribe → `tasks/get`, in that order, all the way down.** Streaming gives the richest live view; if the connection drops, resubscribing gets you back with a full snapshot instead of a gap; if the task already finished and got evicted from active tracking before you resubscribed, `tasks/get` is the fallback that always works because it doesn't depend on live tracking at all. A client that only implements the first rung breaks the moment reality doesn't cooperate. → `resubscribe_demo.py`

**5. Treat push notifications as an optimization, never a guarantee.** Delivery is explicitly best-effort — the server logs a failed POST and moves on, nothing more. Pair every webhook registration with a timeout and a polling fallback; "wait forever for the callback" isn't a resilience strategy, it's a hang waiting to happen. → `webhook_fallback_demo.py`

**6. Decide your own timeout, and expect canceling an already-finished task to fail loudly, not silently.** A2A gives you `tasks/cancel` and `TaskNotCancelableError`; it has no opinion on how long is too long. Pick a budget, cancel when it's blown, and treat `TaskNotCancelableError` on a second attempt as confirmation the first cancel worked — not a bug. → `cancel_demo.py`

**7. Only retry what's actually retriable — a version mismatch isn't.** Distinguish transport-level failures (`A2AClientError`, connection errors — worth backing off and retrying) from protocol-level ones (`VersionNotSupportedError`, `InvalidParamsError` — retrying changes nothing; they need a code fix or a different agent). A retry loop that can't tell these apart just burns time re-sending a request that will fail identically every time. → `retry_demo.py`, `version_mismatch_demo.py`

**8. Watch for retry-triggered duplicate work — a gap our own demo doesn't close.** `retry_demo.py`'s simulated flake fails at the transport layer, before any bytes reach the server, so retrying there is free — the agent never saw the earlier attempts. Real flakes aren't always that polite: if a request reaches the server and starts a task, but it's the *response* that gets lost, blindly retrying with a freshly-generated message risks spinning up a second, redundant task. A production-grade client would reuse the same message/task ID across retries of the same logical request, so a server that already started the work recognizes it instead of doing it twice — worth flagging plainly as a real risk, since nothing in this PoC actually exercises it.
