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

1. Synchronous
2. Polling
3. Server Sent Events
4. Push notifications


## 4. PoC — Designing a System with A2A
4a. Scenario

- Pick a task with genuine long-running + human-in-the-loop shape (this is where A2A's value actually shows, per Section 2b) — e.g., an agent that needs approval mid-task, not just a quick lookup 
4b. Build

- Stand up one A2A agent (server side) and one caller (client side), agent card, task lifecycle 
4c. Design for SSE / long-running work

- Implement streaming updates via SSE, show a dropped-connection-and-resubscribe scenario, confirm it replays a full snapshot rather than losing state
4d. Design for failures — and the fix for each

Failure	What A2A gives you	What you still have to build
Stream drops mid-task	Resubscribe replays full snapshot	Your client's reconnect logic
Webhook never arrives	It's best-effort by design	Fallback to polling
Forged/tampered agent card	Signature verification	Your own acceptance rule (verifyAgentCard)
Version mismatch	Loud VersionNotSupportedError	Your handling of the error, not silent misreads
Task paused indefinitely	tasks/cancel, TaskNotCancelableError	Your own timeout policy
Network flake	—	Client retry with backoff

4e. What to measure/demo live

- Kill the connection mid-stream, show resubscribe recovering full state 
- Force a version mismatch and show the explicit error vs a silent failure 
- Show a paused task resuming after a real time gap (not just same-session) 
5. Conclusion

- Recap: A2A's overhead each pays for something specific — card because you can't read the other side's code, context-in-request because no shared memory, server-side task because the connection won't outlive the job 
- Restate the boundary from Section 2c: only reach for this when the agent on the other end truly isn't yours

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
