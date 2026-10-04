# AI Engineering — A Learning Path

A hands-on, build-it-yourself journey through AI engineering. Each numbered directory is a
self-contained mini-project that introduces **one core concept** and forces me to implement it
from scratch before reaching for a framework. The modules are ordered by dependency: every one
assumes the previous ones and adds a single new layer.

The whole path keeps rebuilding the **same fundamental loop**, just at higher levels of power:

```
prompt → model → tools → state → memory → orchestration → multi-agent → safety
```

By the end the loop is no longer hand-rolled — it's a graph, it persists across restarts, it
remembers you, it talks, it queries your data, it can *both publish and consume* tools over a
standard protocol (MCP), it can delegate work to a **team of specialist agents**, and every input,
action, and output can be wrapped in **guardrails**. Any AI client can use what it builds, and it
can use any AI server.

> **This is a living repository.** Modules 01–16 are done; more topics are still being learned
> and new directories will keep appearing. See [What's Next](#whats-next) for the open roadmap.

---

## Table of Contents

- [The Conceptual Arc](#the-conceptual-arc)
- [Concepts Inventory](#concepts-inventory)
- [Module Walkthroughs](#module-walkthroughs)
- [Tools & Frameworks Inventory](#tools--frameworks-inventory)
- [Running the Projects](#running-the-projects)
- [What's Next](#whats-next)

---

## The Conceptual Arc

The path moves through seven broad stages. Each stage answers a question the previous one raises.

| Stage | Modules | The question it answers |
| --- | --- | --- |
| **1. The raw model** | 01–03 | How does an LLM actually see text, how do I steer it, and how do I expose it over HTTP? |
| **2. Agents from scratch** | 04 | How do I give a model the ability to *act* (call tools) instead of just talk? |
| **3. Retrieval (RAG)** | 05–06 | What if the knowledge isn't in the model's weights? How do I feed it my own documents—and scale that? |
| **4. Orchestration & memory** | 07–10 | How do I structure complex agent logic, keep it alive across restarts, and make it remember long-term? |
| **5. Interfaces & real data** | 11–14 | How do agents speak (voice), query real databases (SQL), publish themselves as reusable tools (MCP server), and consume external tools (MCP client)? |
| **6. Multi-agent systems** | 15 | How do I coordinate several specialists—each with its own loop—instead of one agent doing everything? |
| **7. Safety & guardrails** | 16 | How do I keep the agent from leaking private data, running dangerous actions, or producing unsafe output? |

---

## Concepts Inventory

The *ideas* learned, independent of any library. This is the durable knowledge; the tools below
are just how each idea gets implemented.

**Foundations**
- **Tokenization** — text is split into tokens, not characters or words; the model only ever sees token IDs; token count governs cost and context-window limits.
- **Context windows & encodings** — every model family has its own encoding scheme (`o200k_base` for GPT-4o, etc.).
- **Prompt engineering** — controlling output purely through the input: instructions, examples, and framing.
- **Zero / one / few-shot prompting** — the spectrum from "no examples" to "several worked examples that define the expected shape".
- **Chain-of-Thought (CoT)** — forcing the model to externalize intermediate reasoning steps before answering, which improves reliability on complex tasks.
- **Personas & system prompts** — fixing the model's identity, scope, and refusal behavior up front.

**Agents & reasoning**
- **The agent loop** — an explicit state machine: `START → PLAN → TOOL_CALL → TOOL_RETURN → OUTPUT`.
- **Tool / function calling** — the model emits a structured request to run external code; your loop executes it and feeds the result back.
- **Structured generation** — constraining output to a schema (JSON mode, Pydantic models) so code can consume it deterministically.
- **Guardrails by design** — e.g. read-only DB users, scoped tools, refusal behavior.

**Retrieval**
- **Embeddings** — turning text into vectors where semantic similarity = geometric closeness.
- **Vector search** — nearest-neighbor lookup over those vectors.
- **Chunking & indexing** — splitting documents into overlapping chunks and storing them so they can be retrieved later.
- **RAG (Retrieval-Augmented Generation)** — retrieve relevant context, inject it into the prompt, and ground the answer in your data.
- **Async job queues** — offloading slow work (embedding, generation) to background workers to keep an API responsive and horizontally scalable.

**Orchestration & state**
- **Graph-based orchestration** — modeling agent logic as nodes and edges instead of `if/else` soup.
- **Conditional routing & loops** — sending the flow down different edges based on state, and cycling back to retry/improve.
- **Checkpointing / persistence** — saving graph state to a database so a conversation survives a process restart.
- **Thread IDs** — labelling which conversation a message belongs to, so one store can hold many independent sessions.
- **Short-term vs long-term memory** — in-context message history vs. extracted facts persisted outside the context window.
- **Semantic memory extraction** — the memory layer itself deciding what's worth remembering.
- **Vector memory vs. graph memory** — flat similarity recall vs. entities and relationships that capture *how* facts connect.

**Interfaces & real data**
- **Multimodal pipelines** — chaining STT → LLM → TTS for a voice agent.
- **Text-to-SQL agents** — discovery → schema inspection → query → error recovery → synthesis.
- **The Model Context Protocol (MCP)** — a standard client-server protocol (JSON-RPC 2.0) so any AI host can use any tool, collapsing `N × M` bespoke integrations into `N + M`.
- **MCP server vs. MCP client** — *publishing* capabilities (tools / resources / prompts) versus *discovering and invoking* them. The client re-runs the agent loop from module 04, but the tools are now remote, described by the protocol, and discovered at runtime instead of hardcoded.

**Multi-agent systems**
- **Supervisor / orchestrator pattern** — one coordinating agent that delegates to specialist worker agents and synthesizes their results, instead of a single generalist juggling every domain.
- **Subagents as tools** — exposing an entire agent as a single callable tool, so the supervisor treats a whole specialist like any other function.
- **Scratchpad isolation** — a subagent's messy internal loop (failed queries, intermediate reasoning) stays trapped inside it; only a concise result crosses the boundary, keeping the supervisor's context clean.
- **Domain specialization** — decomposing a broad task into narrow experts (calendar, email, SQL) rather than one prompt with dozens of tools.
- **Handoff / state-machine pattern** — instead of many agents, a *single* agent that transitions through stages, hot-swapping its system prompt and tools at each step based on tracked `current_step`.
- **Dynamic tool & prompt swapping (middleware)** — intercepting every model call (`@wrap_model_call`) to inject only the prompt and tools relevant to the current stage, with `requires` guardrails that halt if a stage's prerequisite data is missing.
- **Tool-driven control flow (`Command`)** — a tool returning a `Command(update={...})` that mutates shared state and advances the stage, so *tools* drive the workflow instead of an external router.
- **Router / fan-out–fan-in (scatter-gather)** — an upfront classification step decomposes a query into source-specific sub-questions, dispatches them to specialists *in parallel*, then a synthesis node merges the results — a fixed, deterministic topology decided before any agent runs.
- **Parallel fan-in via state reducers** — an additive reducer (`Annotated[list, operator.add]`) safely concatenates the outputs of concurrent branches without races or overwrites.

**Safety & guardrails**
- **Guardrails as middleware** — safety checks are interceptors wrapped *around* the agent, not prompt instructions; they inspect and mutate data flowing in and out at fixed choke points.
- **The three gates** — *before agent* (input gate: block bad prompts early), *around model & tool calls* (action gate: sanitize parameters, pause for approval), and *after agent* (output gate: verify the final answer before the user sees it).
- **Deterministic vs. model-based** — regex/rules are fast, cheap, and predictable; a second "judge" LLM understands context but adds latency and cost. Production stacks both.
- **PII detection & sanitization** — catching emails, credit cards, API keys, etc. before they reach the model or logs, with strategies `redact` / `mask` / `hash` / `block`.
- **Human-in-the-loop (HITL)** — pausing a high-stakes tool call so a person can approve, edit, or reject it before execution resumes.
- **Defense-in-depth** — layering guardrails sequentially (keyword filter → PII redaction → agent → human approval → output safety) instead of trusting any single check.
- **Custom middleware hooks** — `before_agent` / `after_agent` hooks (plus model/tool hooks) let you write bespoke guardrails; a blocked hook can short-circuit with `jump_to="end"`.

---

## Module Walkthroughs

Each entry gives the **concept** first (why it exists), then what was actually built and with what.

### 01 — Tokenization
**Concept:** Before any prompting, an LLM is just math over integers. This module makes that
concrete: text is encoded into token IDs and decoded back. It's the foundation for understanding
context limits and cost.

**Built:** Encode/decode a string with `tiktoken` using the `gpt-4o` encoding.
**Key file:** `01_Tokenization/main.py`

---

### 02 — Prompt Techniques
**Concept:** The full spectrum of controlling a model through input alone — how the *same* model
behaves completely differently based on framing. Four independent experiments.

**Built:**
- `oneshot.py` — a bare system instruction ("math only") that the model must respect.
- `fewshot.py` — several worked Q/A examples that teach the model both the format *and* the refusal behavior.
- `cot.py` — a Chain-of-Thought loop that forces strict `START / PLAN / OUTPUT` JSON reasoning steps, one per turn.
- `persona.py` — a deep persona ("Touka", a historian) with identity, scope, and refusal rules, written in raw chat-template format.

**Key files:** `02_Prompt_Techniques/{oneshot,fewshot,cot,persona}.py`

---

### 03 — FastAPI
**Concept:** A model is useless in a script if nothing can reach it. This is the minimal step
from "local script" to "HTTP service" — the shape every later service follows.

**Built:** A one-endpoint FastAPI app returning JSON.
**Key file:** `03_FastApi/server.py`

---

### 04 — Weather Agent
**Concept:** The leap from *chatbot* to *agent*. The model can't fetch live weather, so we teach
it to call a tool. This module hand-rolls the entire agent loop that frameworks later hide.

**Built:** A `START/PLAN/TOOL_CALL/TOOL_RETURN/OUTPUT` state machine where the model emits JSON,
the loop executes `get_weather` (via `wttr.in`) and feeds the result back. Three escalating versions:
- `main.py` — a plain chatbot baseline.
- `agent.py` — full tool-calling agent loop with JSON parsing.
- `structured_output.py` — same loop but schema-constrained with Pydantic (adds a `run_cmd` tool too), so output is validated instead of string-parsed.

**Key files:** `04_weather_agent/{main,agent,structured_output}.py`

---

### 05 — RAG
**Concept:** "What does the model know?" becomes "what can I *retrieve*?" Split a PDF into
overlapping chunks, embed them into vectors, store them, then search by meaning at query time and
inject the top matches into the prompt as grounding context.

**Built:** Two stages — an **indexing** script (load → split → embed → store in Qdrant) and a
**chat** script (similarity search → build context with page numbers and file locations → answer).
**Key files:** `05_RAG/index.py`, `05_RAG/chat.py`
**Infra:** `docker-compose.yml` runs Qdrant.

---

### 06 — RAG Queue
**Concept:** RAG is slow. Holding an HTTP request open while you embed and generate doesn't scale.
This module decouples *submission* from *processing* with a job queue: the API enqueues work and
returns a job ID; background workers do the heavy lifting. This is how you scale horizontally —
just add more workers.

**Built:** A FastAPI service that enqueues queries into **RQ** (Redis/Valkey-backed), plus a
**worker** that performs the full retrieval + generation and returns the result via a `/result`
polling endpoint.
**Key files:** `06_RAG_queue/server.py`, `queues/worker.py`, `client/rq_client.py`
**Infra:** `docker-compose.yml` runs Valkey + Qdrant.

---

### 07 — Langgraph
**Concept:** Hand-written agent loops (module 04) don't scale to complex logic. **LangGraph** models
an agent as a graph: **nodes** (functions), **edges** (transitions), and **shared state** passed
between them. This is where orchestration becomes a first-class design tool.

**Built:**
- `chat.py` — a minimal graph: state as an annotated message list, two nodes wired `START → chat → sampleNode → END`.
- `smart_routing.py` — the important one: **conditional edges** that branch on state (a human "is the response good?" check) and **loop back** to a second chatbot to retry — the graph equivalent of a retry/self-improvement loop.

**Key files:** `07_Langgraph/{chat,smart_routing}.py`

---

### 08 — Persistence
**Concept:** An agent that forgets everything on restart isn't an assistant. **Checkpointing** saves
graph state to a database so a conversation resumes exactly where it left off. The key handle is the
**`thread_id`** — a per-conversation label that lets one store hold many separate sessions.

**Built:** A LangGraph chatbot compiled with a `MongoDBSaver` checkpointer, storing message history in
MongoDB keyed by thread. Message accumulation is done with `Annotated[list, operator.add]`.
**Key files:** `08_Persistence/chat.py`
**Infra:** `docker-compose.yml` runs MongoDB.

---

### 09 — AI Agents Memory
**Concept:** Checkpointing stores *raw message history* (short-term). Real memory is different: the
system should **extract durable facts** about the user and recall them later — long-term semantic
memory that lives outside the context window. This module introduces **mem0** as that memory layer.

**Built:** A loop that (1) searches memory for relevant facts about user `ken`, (2) injects them into
the system prompt, (3) answers, then (4) writes the new exchange back into memory for extraction.
**Key files:** `09_AI_Agents_Memory/mem.py`
**Infra:** `docker-compose.yml` runs Qdrant. Embeddings via HuggingFace, LLM via the OpenAI-compatible client.

---

### 10 — Graph Memory
**Concept:** Vector memory recalls *similar* facts but loses *relationships*. **Graph memory** stores
entities and edges (e.g. "Alex —works_at→ X"), so the agent can reason over connections, not just
similarity. This is the "why graph over vector DB?" module.

**Built:** The same mem0 loop as module 09, but with an added **Neo4j graph store** alongside Qdrant —
mem0 writes both a vector representation and a knowledge graph.
**Key files:** `10_Graph_Memory/main.py`
**Infra:** `docker-compose.yml` runs Qdrant; Neo4j is external (see `.env`).

---

### 11 — Voice Agents
**Concept:** A complete **multimodal pipeline** — the agent's final form as an interface. Speech →
text → reasoning → speech. Nothing exotic: it's the same `prompt → model` loop, just wrapped in
input/output modalities.

**Built:** `STT` (SpeechRecognition + microphone) → `LLM` → `TTS` (Kokoro ONNX). A system prompt
shapes the response so it sounds natural when spoken back.
**Key files:** `11_Voice_agents/main.py` (setup notes in `readme.md`)
**Note:** large model weights (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) are downloaded, not committed.

---

### 12 — SQL Analyst
**Concept:** The capstone agent: **tool calling over a real database**. The model can't query Postgres
directly, so it's given a discovery workflow — list tables, inspect schema, write SQL, execute, recover
from errors, synthesize — and is **constrained to read-only** both by prompt and by a locked-down DB
user. Safety by design, not by hope.

**Built:** A LangChain tool-calling agent (`list_tables`, `describe_tables`, `exec_sql`) over the
**Northwind** PostgreSQL sample database. Includes a `02_readonly.sql` lockdown and a populated
`northwind.sql` loaded automatically on container start.
**Key files:** `12_SQL_Analyst/main.py`, `docker-compose.yml`, `northwind.sql`, `02_readonly.sql`
**Infra:** Postgres + pgAdmin via `docker-compose.yml`.

---

### 13 — MCP Server (Model Context Protocol)
**Concept:** Every previous module exposed tools *custom* to one app. **MCP** is the standard that
makes tools universally pluggable — "USB-C for AI integrations". Instead of `N × M` bespoke
integrations, both sides speak one protocol (JSON-RPC 2.0) and anything interoperates. This module
is the **publishing** side of that pair. It also introduces proper Python packaging (`uv`,
`pyproject.toml`) since an MCP server is a distributable artifact.

**Built:** A weather MCP **server** exposing a `weather` tool over stdio, runnable in the MCP
Inspector or any MCP host (Claude Desktop, etc.). Its own `README.md` is a full deep-dive on hosts,
clients, servers, transports, primitives, and lifecycle.
**Key files:** `13_MCP_Server/src/weather_mcp/server.py`, `13_MCP_Server/README.md`, `pyproject.toml`

---

### 14 — MCP Client
**Concept:** The other half of the protocol — the **consuming** side. A client connects to a server,
completes the `initialize` handshake, discovers what the server offers (`tools/list`), and invokes
it (`tools/call`). The important part: the client **re-implements the agent loop from module 04**,
but the tools are no longer hardcoded — they're fetched from the server at runtime, handed to the
LLM as standard function definitions, and executed over MCP in a *separate process*. This is what
closes the loop: module 13 taught the agent to be a server, module 14 teaches it to be the host.

**Built:** A CLI client that spawns the weather server as a **stdio child process**, discovers its
tools, and runs an interactive LLM tool-calling loop against it. It uses `AsyncExitStack` to manage
the dynamic lifetime of the connection and guarantees clean teardown.
**Key files:** `14_MCP_Client/src/mcp_client/__init__.py`, `pyproject.toml`
**Run:** `uv run mcp-client ../13_MCP_Server/src/weather_mcp/server.py`

---

### 15 — Multi-Agent System
**Concept:** One agent with tools for every domain gets a polluted context and blurs its tool
selection. This module explores **three multi-agent orchestration patterns** that each solve that
problem in a different way.

The **supervisor pattern** splits the work: a single orchestrator delegates to focused specialists,
and each specialist is wrapped as a callable **tool**. The user only ever talks to the supervisor;
each subagent runs its own private agent loop and returns one concise string. Crucially, the
subagent's messy internals — failed queries, intermediate reasoning — stay trapped inside it
(**scratchpad isolation**), so the supervisor's context stays clean. This is orchestration one level
up: **agents calling agents**.

The **handoff pattern** takes the opposite shape: instead of many agents, a *single* agent
transitions through stages of a **state machine**, hot-swapping its system prompt and tools at each
step based on a tracked `current_step`. Tools themselves drive the flow — they return
`Command(update={...})` that records data and advances the stage — so the workflow is **an agent
changing its own shape**, not an orchestrator directing peers.

The **router pattern** is a deterministic **fan-out / fan-in** (scatter-gather) graph. An upfront
`classify` step decomposes the query into source-specific sub-questions, a conditional edge fans out
with LangGraph's `Send` to run the relevant specialists **in parallel**, an additive state reducer
merges their outputs, and a `synthesize` node reconciles everything into one answer. Unlike the other
two, the topology is fixed before any agent runs rather than decided turn by turn.

**Built:**
- **Supervisor / subagents** — a LangChain **supervisor** agent (`create_agent`) whose tools are two
  specialist subagents — a **calendar agent** (`create_react_agent` + `create_calendar_event` /
  `get_available_time_slots`) and an **email agent** (`send_email`). Each subagent is wrapped in a
  `call_cal_agent` / `call_email_agent` tool, and the supervisor streams events
  (`messages` + `tool_calls`) as it coordinates multi-step requests.
- **Handoffs (state machine)** — a single LangChain v1 `create_agent` instance with `wrap_model_call`
  middleware that reads `current_step` and hot-swaps the system prompt + tools for the active stage.
  Three stages (`warranty_collector` → `issue_classifier` → `resolution_specialist`), each with
  `requires` guardrails; transition tools return `Command(update={...})` to record data and advance
  state, persisted across turns by an `InMemorySaver` checkpointer.
- **Router (fan-out / fan-in)** — a LangGraph `StateGraph` (`classify → github/notion/slack →
  synthesize`) that fans out via `Send`, collects parallel outputs with an `operator.add` reducer,
  and merges them in a synthesis node. Classification uses structured output
  (`with_structured_output`); the whole graph is exposed to a conversational `create_agent` wrapper
  as the `search_knowledge_base` tool.

**Key files:** `15_Multi_Agent_System/src/subagents/__init__.py`,
`15_Multi_Agent_System/src/subagents/{cal_agent,email_agent}.py` (supervisor),
`15_Multi_Agent_System/src/handoffs/__init__.py` (handoffs),
`15_Multi_Agent_System/src/router/__init__.py` (router)
**Run:** `uv run multi-agent-system` (supervisor), `uv run handoffs` (handoffs state machine),
`uv run router` (fan-out / fan-in router); `uv run calagent` / `uv run emailagent` exercise a
subagent directly

---

### 16 — Guardrails
**Concept:** A capable agent is also one that can leak private data, trigger a destructive action, or
produce unsafe output. **Guardrails** are safety checks implemented as **middleware** — interceptors
that sit at three choke points in the agent lifecycle: *before agent* (input gate), *around model &
tool calls* (action gate), and *after agent* (output gate). They come in two flavors:
**deterministic** (regex/keyword rules — fast, cheap, predictable) and **model-based** (a second
"judge" LLM that understands context). Production systems layer several in sequence — **defense in
depth**.

**Built:** three runnable examples under `src/`, each wiring a different guardrail into a
`create_agent`:
- **PII (`pii_gr`)** — three `PIIMiddleware` rules on the input gate: emails `redact`, credit cards
  `mask`, and API keys (custom `sk-…` regex) `hash`. Prints what the LLM *actually received* vs. what
  was typed.
- **HITL (`hitl`)** — `HumanInTheLoopMiddleware` with an `interrupt_on` map (`search` auto-runs;
  `send_email` and `delete_database` pause). An interactive loop inspects the pending tool + arguments
  and resumes the run with `Command(resume={"decisions": [...]})` to approve or reject.
- **Custom (`custom_gr`)** — hand-written middleware subclassing `AgentMiddleware`:
  `ContentFilterMiddleware` (deterministic `before_agent` keyword block that jumps to `end`) and
  `SafetyGuardrailMiddleware` (model-based `after_agent` judge that redacts unsafe output).

**Key files:** `16_Guardrails/src/{pii_gr,hitl,custom_gr}/__init__.py`, `16_Guardrails/README.md`
**Run:** `uv sync`, then `uv run pii-gr`, `uv run hitl`, `uv run custom-gr`
(each reads `CMD_API_KEY` / `CMD_BASE_URL` from `.env`)

---

## Tools & Frameworks Inventory

The libraries used, what each one *is*, and where it first appears. Separate the concept (above)
from the tool: the tool is swappable, the concept is not.

| Tool / Framework | What it is | Used here for | First seen |
| --- | --- | --- | --- |
| **tiktoken** | OpenAI's tokenizer library | Encoding/decoding text into tokens | 01 |
| **OpenAI Python SDK** | Client for OpenAI-compatible APIs | Talking to the model (points at a local OpenAI-compatible server) | 02 |
| **FastAPI** | Async Python web framework | Exposing apps/models as HTTP endpoints | 03 |
| **requests** | HTTP client | Fetching live weather from `wttr.in` | 04 |
| **Pydantic** | Data validation library | Schema-constrained structured output | 04 |
| **python-dotenv** | `.env` file loader | Loading API keys and base URLs from the environment | 04 |
| **LangChain** | LLM application framework | PDF loaders, text splitters, agents, vector-store integrations | 05 |
| **sentence-transformers / HuggingFace** | Local embedding models | Turning text into vectors (`all-MiniLM-L6-v2`) | 05 |
| **Qdrant** | Vector database | Storing and searching embeddings | 05 |
| **PyPDF** | PDF parser | Loading PDF documents into LangChain | 05 |
| **RQ (Redis Queue)** | Background job queue | Offloading RAG work to workers | 06 |
| **Redis / Valkey** | In-memory data store | Backing store for the job queue | 06 |
| **uvicorn** | ASGI server | Running FastAPI apps | 06 |
| **LangGraph** | Graph orchestration for agents | Nodes/edges/state, conditional routing, loops | 07 |
| **MongoDB** | Document database | Persisting conversation checkpoints | 08 |
| **mem0** | Memory layer for AI agents | Extracting and recalling long-term memory | 09 |
| **Neo4j** | Graph database | Storing memory as entities + relationships | 10 |
| **SpeechRecognition** | STT wrapper | Transcribing microphone audio | 11 |
| **Kokoro ONNX** | Local TTS model | Converting text responses to speech | 11 |
| **sounddevice** | Audio I/O | Playing synthesized speech | 11 |
| **SQLAlchemy** | Python SQL toolkit | Connecting to and querying Postgres | 12 |
| **PostgreSQL** | Relational database | The Northwind database the agent queries | 12 |
| **pgAdmin** | Postgres web UI | Inspecting the database | 12 |
| **MCP Python SDK** | Model Context Protocol SDK | Building the MCP **server** (13) *and* the **client** that connects to it and calls its tools (14) | 13–14 |
| **httpx** | Async HTTP client | Calling `wttr.in` from the MCP tool | 13 |
| **uv** | Fast Python package/project manager | Managing deps, lockfile, and the runnable scripts | 13–16 |
| **contextlib.AsyncExitStack** | Python stdlib async resource manager | Managing the MCP client connection's dynamic lifetime and clean teardown | 14 |
| **LangChain `create_agent` / LangGraph `create_react_agent`** | High-level agent constructors | Building the supervisor, its specialist subagents, the handoff agent, and the router's specialists | 15 |
| **LangGraph `Send` (scatter-gather)** | Fan-out primitive for parallel graph branches | Dispatching one query to several specialist agents at once in the router | 15 |
| **LangChain guardrail middleware** (`PIIMiddleware`, `HumanInTheLoopMiddleware`, `AgentMiddleware`) | Built-in and user-defined interceptors around the agent | Redacting PII, pausing for human approval, and writing custom input/output safety gates | 16 |
| **Docker / Docker Compose** | Container runtime | Running all infrastructure (Qdrant, Redis, Mongo, Postgres, Neo4j) | 05+ |

---

## Running the Projects

Everything targets **Python 3.11**. Heavy infra runs in Docker; model inference runs through an
**OpenAI-compatible local server** (the code points at `http://127.0.0.1:1337/v1`) or any gateway
configured in `.env`.

**Environment variables** (`.env`, mirrored in `.env.example`):

```
NEO_USERNAME=
NEO_PASSWORD=
NEO_URI=
CMD_API_KEY=
CMD_BASE_URL=
POSTGRES_URL=
```

**General setup:**

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Infrastructure:** most modules ship a `docker-compose.yml`. From the relevant directory:

```bash
docker compose up -d
```

| Module | Compose brings up | Port(s) |
| --- | --- | --- |
| 05_RAG | Qdrant | 6333 |
| 06_RAG_queue | Valkey, Qdrant | 6379, 6333 |
| 08_Persistence | MongoDB | 27017 |
| 09_AI_Agents_Memory | Qdrant | 6333 |
| 10_Graph_Memory | Qdrant (+ external Neo4j) | 6333 |
| 12_SQL_Analyst | Postgres, pgAdmin | 5432, 5050 |

Modules 01–04, 07, 11, 15 and 16 need no containers. Modules 13–16 are `uv` projects: 13 (**server**)
and 14 (**client**) talk over local **stdio** (the client spawns the server as a child process), while
15 (**multi-agent**) and 16 (**guardrails**) run entirely in-process — see each module's own README
for details.

---

## What's Next

The path is not finished. The same loop keeps gaining layers, and the next installments will add new
directories (17, 18, …) as each topic is learned. Directions still open:

- **Advanced retrieval** — hybrid search (BM25 + vectors), reranking, query rewriting, evaluation of retrieval quality.
- **Advanced multi-agent topologies** — beyond the supervisor, handoff, and router patterns: hierarchical teams, peer-to-peer handoff, and shared-vs-isolated memory between agents.
- **Remote & multi-server MCP** — the `streamable-http`/`sse` transports for networked servers, and a client that aggregates tools from several servers at once.
- **Agent evaluation & observability** — tracing, LangSmith, measuring accuracy instead of eyeballing output.
- **Fine-tuning vs. prompting** — when to adapt weights instead of prompts.
- **Deeper security** — beyond the module-16 guardrail basics: prompt-injection defenses, red-teaming, scoped permissions, and auth.
- **Deployment** — containerizing and shipping these services for real.
- **Structured data at scale** — from the SQL agent toward full analytics-on-natural-language.

New modules will follow the same convention: a numbered directory, one concept, one working project.

---

*This README is a map, not a textbook — each module is meant to be read alongside its own code and,
where present, its own README. Start at 01 and follow the numbers; every module depends on the ones before it.*
