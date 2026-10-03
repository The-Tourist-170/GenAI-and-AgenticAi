# Multi-Agent System

A hands-on exploration of three multi-agent orchestration patterns built with LangChain and
LangGraph:

- **Subagents** — a supervisor/worker hierarchy where specialists are exposed as tools.
- **Handoffs** — a single agent that transitions through stages via a state machine.
- **Router** — a deterministic fan-out / fan-in (scatter-gather) graph.

---

## Table of Contents

- [Subagents](#subagents)
- [Handoffs](#handoffs)
- [Router](#router)

---

## Subagents

The **subagent (supervisor) pattern** is a hierarchical multi-agent architecture where a central
"supervisor" agent coordinates specialized worker agents that are packaged and exposed as
high-level tools.

Instead of burdening one giant agent with dozens of disparate API tools and massive prompt
instructions, you split the work into domain specialists (e.g., calendar, email, SQL). The
supervisor never interacts with low-level API calls directly — it only sees high-level functions
like `schedule_event` or `manage_email` and delegates natural language tasks down to them.

### Subagents vs. Handoffs

| Dimension | Subagents Pattern (Hierarchical) | Handoffs Pattern (State Machine) |
| --- | --- | --- |
| **Control Model** | **Call-and-Return:** The supervisor retains master control, invokes a subagent, waits for its output, and keeps moving. | **State Transfer:** The current agent hands off total control to another stage/agent; the previous stage is finished. |
| **User Interface** | The user **only talks to the supervisor**. Subagents run entirely behind the scenes. | The user converses with whatever agent/stage currently holds active control. |
| **Tool Visibility** | **Layered abstraction:** The supervisor only sees subagents as tools; subagents see the actual low-level API tools. | **Flat dynamic swapping:** The active agent has direct access to the tools needed for its specific stage. |
| **Best Used For** | Multi-domain delegation and task coordination (e.g., "Check my calendar and email the team"). | Phased, sequential workflows (e.g., triage → troubleshooting → payment/escalation). |

### The Flow of Subagents (Step-by-Step)

The supervisor architecture operates across three distinct operational layers:

```text
[ User Request ]
       │
       ▼
1. Supervisor Agent (Top Layer)
   - Evaluates high-level intent
   - Decides which specialist tools to invoke
       │
       ▼
2. Tool Wrapper (`@tool def schedule_event(request)`)
   - Translates supervisor intent into a subagent prompt
       │
       ▼
3. Specialized Subagent (Middle Layer)
   - Operates in its own isolated reasoning loop
   - Parses dates, reasons, crafts messages
       │
       ▼
4. Low-Level Tools (Bottom Layer)
   - Exact API calls: `create_calendar_event`, `send_email`
   - (Optional) Human-in-the-Loop review interrupts execution
       │
       ▼
5. Return & Synthesis
   - Subagent finishes and returns final text to the wrapper
   - Wrapper returns plain string back to supervisor scratchpad
   - Supervisor synthesizes outputs and responds to user
```

#### Detailed Phase Walkthrough

1. **Ingestion & High-Level Planning**
   - The user sends a complex request: *"Schedule a meeting next Tuesday at 2pm for 1 hour, and email the design team a reminder."*
   - The supervisor inspects its available tools (`schedule_event`, `manage_email`). It does **not** know how to query calendars or format SMTP payloads — it only knows which agent handles which domain.

2. **Subagent Invocation (Tool Call)**
   - The supervisor issues a tool call: `schedule_event(request="meeting with design team next Tuesday at 2pm for 1 hour")`.
   - Execution enters the wrapper function, which triggers `calendar_agent.invoke(...)`.

3. **Isolated Subagent Execution**
   - The calendar agent boots up its own context window.
   - It translates "next Tuesday at 2pm" into an exact ISO timestamp (`2024-06-18T14:00:00`) and calls low-level tools (`get_available_time_slots`, `create_calendar_event`).
   - Any errors, retries, or schema-formatting attempts happen inside this subagent — completely hidden from the supervisor.

4. **Human-in-the-Loop (Optional Interruption)**
   - If a subagent calls a high-stakes tool (like `send_email`), middleware pauses execution before running the function.
   - The system presents the exact payload to the user for approval, editing, or rejection via a `Command(resume=...)`.

5. **Output Synthesis**
   - The subagent completes its work and returns a natural language summary to the wrapper function.
   - The wrapper returns that summary string to the supervisor as the tool result.
   - The supervisor either calls the next subagent (`manage_email`) or combines all results into a unified, polite response for the user.

---

## Handoffs

A **handoff** is a design pattern where an agent workflow transitions control, instructions, and
available tools from one stage of a task to the next as the conversation progresses.

In the implementation shown in the documentation, handoffs are achieved using a **state machine**:
rather than spawning multiple distinct agents, a single persistent agent dynamically shifts its
personality (system prompt) and capabilities (tools) turn-by-turn based on a tracked
`current_step` in its state.

### Handoffs vs. Subagents

| Feature | Subagents Pattern (Hierarchical) | Handoffs Pattern (State Machine) |
| --- | --- | --- |
| **Architecture** | Parent/Supervisor agent + isolated child agents | A single agent transitioning through states (or peers passing control) |
| **Execution Model** | **Call-and-return**: Supervisor calls the subagent like a tool, waits for the result, and continues | **State transition**: The workflow moves forward (or backward) to a new step; the old step is left behind |
| **Who Talks to the User?** | Always the supervisor (the subagent's scratchpad is hidden) | The active stage itself handles the user interaction directly |
| **Tool Availability** | Subagents are exposed as callable functions (`call_email_agent`) | Tools are hot-swapped dynamically based on the current step |
| **Best Used For** | Multi-domain delegation (e.g., orchestrator coordinating SQL + Calendar + Email) | Sequential, phased conversations (e.g., Intake → Triage → Resolution → Escalation) |

### The Flow of Handoffs (Step-by-Step)

The handoff flow operates as a closed loop between **Tools**, **State**, and **Middleware**:

```text
[ User Message ]
       │
       ▼
1. Middleware Reads State (`current_step`)
       │
       ▼
2. Dynamic Configuration Applied (Prompt + Tools hot-swapped)
       │
       ▼
3. Agent Decides & Runs a Transition Tool
       │
       ▼
4. Tool Returns `Command(update={"current_step": "next_step", ...})`
       │
       ▼
5. State Checkpointed ──► Next Turn Starts at New Step
```

#### Detailed Phase Walkthrough

1. **Intake / Default State**
   - The conversation begins with `current_step = "warranty_collector"`.
   - Middleware intercepts the turn, loads the `WARRANTY_COLLECTOR_PROMPT`, and restricts the agent to only one tool: `record_warranty_status`.
   - The agent asks the user if their device is under warranty.

2. **Tool-Driven Handoff**
   - The user answers: *"Yes, it's covered."*
   - The agent calls `record_warranty_status("in_warranty")`.
   - Instead of just returning a string, the tool returns a `Command` object that updates the shared state:
     - Saves data: `warranty_status = "in_warranty"`
     - Advances stage: `current_step = "issue_classifier"`

3. **State Reconfiguration**
   - On the next interaction, the checkpointer loads the updated state.
   - Middleware detects `current_step == "issue_classifier"`.
   - It injects the new prompt (`ISSUE_CLASSIFIER_PROMPT`) containing the saved warranty data and swaps the active tools to `[record_issue_type]`.

4. **Resolution or Escalation**
   - The agent determines the problem is hardware-related and calls `record_issue_type("hardware")`.
   - State updates to `current_step = "resolution_specialist"`.
   - The final step activates tools like `provide_solution` and `escalate_to_human`.

5. **Session Persistence**
   - An `InMemorySaver` checkpointer stores `current_step`, `warranty_status`, and `issue_type` after every turn.
   - Each new user message resumes from the checkpointed stage, so the state machine never loses its place between turns.

### Implementation

The handoff pattern is implemented in [`src/handoffs/__init__.py`](src/handoffs/__init__.py) and
runs as the `handoffs` console command (`uv run handoffs`). A deeper developer guide covering the
`AgentState`, `ToolRuntime`, and `Command` primitives lives in
[`src/handoffs/README.md`](src/handoffs/README.md).

The agent is a single LangChain v1 `create_agent` instance (`state_schema=SupportState`,
`middleware=[apply_step_config]`, `checkpointer=InMemorySaver()`) rather than a manually assembled
`StateGraph`.

It moves through three stages tracked by `current_step` in `SupportState`:

| Stage | Tools Available | Requires |
| --- | --- | --- |
| `warranty_collector` | `record_warranty_status` | — |
| `issue_classifier` | `record_issue_type` | `warranty_status` |
| `resolution_specialist` | `provide_solution`, `escalate_to_human` | `warranty_status`, `issue_type` |

The `apply_step_config` middleware (decorated with `@wrap_model_call`) intercepts every model
request, reads `current_step`, enforces the `requires` guardrails, and calls `request.override(...)`
to hot-swap the system prompt and tools for the active stage. Each transition tool returns a
`Command(update={...})` that records its data and advances `current_step`; an `InMemorySaver`
checkpointer persists that state across turns.

---

## Router

The **router pattern** is a multi-agent architecture that uses an upfront classification step to
analyze a user query, decompose it into domain-specific sub-questions, dispatch them to specialized
vertical agents in parallel, and synthesize the collective findings into a single unified response.

Unlike an open-ended agent loop that discovers tools on the fly, a router enforces an explicit
**fan-out / fan-in (scatter-gather)** pipeline built on top of a directed state graph.

### Router vs. Subagents vs. Handoffs

| Feature | Router Pattern (Fan-Out / Fan-In) | Subagents Pattern (Hierarchical) | Handoffs Pattern (State Machine) |
| --- | --- | --- | --- |
| **Control Flow** | **Deterministic Graph**: Classify → Parallel Execution → Synthesize | **Dynamic Delegation**: Supervisor calls child agents as tools whenever needed | **State Progression**: Agent transitions from stage to stage over multiple turns |
| **Concurrency** | **Native Parallel**: Fans out to multiple agents simultaneously via `Send` | Primarily **Sequential**: Tools run one after another (unless parallel tool calling triggers) | **Single Active Node**: Only one stage/agent handles the user at a time |
| **Query Handling** | **Deconstructs** the query into tailored sub-questions per source | Passes raw or translated tasks down to worker tools | Persists context across the conversation turns |
| **Output Assembly** | An explicit **Synthesis Node** merges and reconciles all agent results | The **Supervisor** summarizes results after all tool calls return | The **Active Stage** responds directly to the user |
| **Best Used For** | Multi-source search, knowledge retrieval across silos (GitHub, Notion, Slack) | Multi-domain action orchestration (e.g., check calendar → send email) | Phased conversational workflows (e.g., triage → intake → resolution) |

### The Flow of the Router Pattern (Step-by-Step)

The router workflow operates through four coordinated phases in a LangGraph `StateGraph`:

```text
               [ User Query ]
                     │
                     ▼
             1. Classify Node
        (Decompose query via Pydantic)
                     │
         ┌───────────┼───────────┐
         ▼ (Send)    ▼ (Send)    ▼ (Send)
    [ GitHub ]   [ Notion ]   [ Slack ]   <-- 2. Parallel Fan-Out
         │           │           │
         └───────────┼───────────┘
                     ▼ (Reducer: operator.add)
             3. Collect Results
                     │
                     ▼
             4. Synthesize Node
         (Reconcile & deduplicate)
                     │
                     ▼
             [ Combined Answer ]
```

#### Detailed Phase Walkthrough

1. **Classify & Decompose**
   - The user asks a broad question: *"How do I authenticate API requests?"*
   - The `classify` node uses structured output (`with_structured_output(ClassificationResult)`) to evaluate which knowledge bases are relevant.
   - Instead of forwarding the raw prompt, it writes custom, optimized sub-queries for each selected domain:
     - **GitHub sub-query:** *"What authentication code exists? Search for auth middleware, JWT handling."*
     - **Notion sub-query:** *"What authentication documentation exists? Look for API auth guides."*
   - *(Slack is omitted completely because it is not needed.)*

2. **Parallel Routing (`Send` API)**
   - A conditional edge function (`route_to_agents`) inspects the classifications.
   - It returns a list of `Send("node_name", {"query": "..."})` objects.
   - LangGraph fans out and boots the selected agents **simultaneously in parallel**, cutting total response latency down to the speed of the slowest single agent.

3. **Specialist Agent Execution**
   - Each vertical agent (GitHub, Notion, Slack) receives a minimal `AgentInput` containing only its specific sub-question.
   - Agents execute their domain-specific tools (e.g., `search_code`, `search_prs`, `search_notion`) without knowing the other agents exist.

4. **Fan-In via State Reducers**
   - Each agent returns an `AgentOutput` dict: `{"results": [{"source": "github", "result": "..."}]}`.
   - The parent graph state defines `results` with an additive reducer (`Annotated[list[AgentOutput], operator.add]`).
   - As parallel branches finish, their outputs are concatenated safely into a single shared list without race conditions or state overwrites.

5. **Synthesis**
   - Once all dispatched agent branches hit completion, execution converges on the `synthesize` node.
   - An LLM call reviews the aggregated findings, strips out redundant text, flags any conflicting information between sources, and formats a clean, comprehensive answer for the user.
