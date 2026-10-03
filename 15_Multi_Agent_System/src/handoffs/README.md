# Advanced State Management & Tool Control in LangGraph

A developer guide to coordinating memory, tool execution, and dynamic graph routing using `AgentState`, `ToolRuntime`, and `Command`.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Primitives](#core-primitives)
- [Complete End-to-End Implementation](#complete-end-to-end-implementation)
- [Execution Lifecycle](#execution-lifecycle)
- [Best Practices](#best-practices)
- [The Dynamic Stage Manager (Middleware)](#the-dynamic-stage-manager-middleware)

---

## Architecture Overview

In standard LLM tool execution, tools act as black boxes: an LLM supplies arguments, the tool executes, and it returns a string back to the model.

Complex agents require deeper coordination:

- Tools must read from or modify graph memory directly.
- Tools need runtime execution metadata (such as `tool_call_id`) without burdening the LLM with passing system parameters.
- Tools must be able to redirect workflow transitions dynamically.

```text
┌─────────────────────────────────────────────────────────────┐
│                         AgentState                          │
│   (Shared Memory: messages, warranty_status, current_step)  │
└───────────────┬─────────────────────────────▲───────────────┘
                │ Reads State                 │ Updates State
                ▼                             │
       ┌─────────────────┐           ┌────────┴────────┐
       │   Agent Node    │           │     Command     │
       │  (LLM Decision) │           │ (update / goto) │
       └────────┬────────┘           └────────▲────────┘
                │ Calls Tool                  │
                ▼                             │ Returns
       ┌─────────────────┐           ┌────────┴────────┐
       │   Tool Engine   ├──────────►│  @tool Function │
       └─────────────────┘ Injects   │  record_status  │
                           ToolRuntime
```

---

## Core Primitives

### 1. `AgentState`

`AgentState` is the agent's centralized memory, implemented as a Python `TypedDict`. It defines every variable tracked across turns and graph nodes.

- **Single Source of Truth:** Retains the conversation thread, domain-specific attributes, session IDs, and intermediate scratchpads.
- **Reducers vs. Overwrites:**
  - By default, returning a key overwrites its existing value in state.
  - Fields wrapped with an `Annotated` reducer (such as `add_messages`) append new entries to lists rather than replacing them.

```python
from typing import Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Literal, TypedDict


class SupportState(TypedDict):
    # Appends new messages; preserves full conversation history
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Directly overwritten when updated
    warranty_status: Literal["in_warranty", "out_of_warranty"] | None
    current_step: str
```

---

### 2. `ToolRuntime`

`ToolRuntime` is an **injected parameter**. It acts as a secure bridge between the workflow execution engine and your tool function.

- **Information Hiding:** Stripped from the JSON schema delivered to the LLM. The model never knows `runtime` exists and cannot hallucinate or tamper with its values.
- **Plumbing Access:** Supplies execution-critical metadata, including:
  - `runtime.tool_call_id`: The provider-issued request identifier (e.g., from OpenAI/Anthropic) required to match a `ToolMessage` with an `AIMessage` tool call.
  - `runtime.state`: Read access to the active snapshot of `SupportState`.
  - `runtime.config`: Graph configurations, thread identifiers, or user secrets.

#### API Schema Contrast

| Perspective | Signature / Representation |
| --- | --- |
| **Python Function** | `def record_warranty_status(status: Literal[...], runtime: ToolRuntime[...])` |
| **LLM JSON Schema** | `{"name": "record_warranty_status", "parameters": {"properties": {"status": {...}}, "required": ["status"]}}` |

---

### 3. `Command`

`Command` transforms a tool from a passive calculator into an active graph controller. Instead of returning plain text to an agent node, a tool returns a `Command` object to apply mutations directly.

- **`update`:** A dictionary specifying changes to commit to `AgentState`.
- **`goto` (Optional):** The identifier of a specific node or sub-agent to transition to next, bypassing standard edge evaluation.

```python
return Command(
    update={
        # 1. Append valid ToolMessage using injected runtime ID
        "messages": [
            ToolMessage(
                content=f"Warranty status recorded: {status}",
                tool_call_id=runtime.tool_call_id,
            )
        ],
        # 2. Mutate domain state
        "warranty_status": status,
        # 3. Update agent workflow state
        "current_step": "issue_classifier",
    },
    goto="issue_classifier_node",  # Optional: direct control flow jump
)
```

---

## Complete End-to-End Implementation

```python
from typing import Annotated, Sequence
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from typing_extensions import Literal, TypedDict

# =====================================================================
# 1. State Definition
# =====================================================================


class SupportState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    warranty_status: Literal["in_warranty", "out_of_warranty"] | None
    current_step: str


# =====================================================================
# 2. Runtime Shim & Tool Definition
# =====================================================================


class ToolRuntime:
    """Mock runtime representing LangGraph's internal tool execution context."""

    def __init__(self, tool_call_id: str, state: SupportState):
        self.tool_call_id = tool_call_id
        self.state = state


@tool
def record_warranty_status(
    status: Literal["in_warranty", "out_of_warranty"],
    runtime: ToolRuntime,
) -> Command:
    """Record customer warranty coverage and prepare for issue classification."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Recorded status: {status}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "warranty_status": status,
            "current_step": "issue_classifier",
        }
    )


# =====================================================================
# 3. Graph Nodes & Routing
# =====================================================================


def support_agent_node(state: SupportState):
    """Simulates agent evaluation deciding to trigger the warranty tool."""
    # Example mock LLM decision generating a tool call
    mock_tool_call = {
        "name": "record_warranty_status",
        "args": {"status": "in_warranty"},
        "id": "call_tx_908123_abc",
    }
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[mock_tool_call],
            )
        ]
    }


def issue_classifier_node(state: SupportState):
    """Next stage in the pipeline consuming state updated by the tool."""
    status = state.get("warranty_status")
    return {
        "messages": [
            AIMessage(content=f"Proceeding with triage under status: {status}.")
        ]
    }


# =====================================================================
# 4. Graph Construction
# =====================================================================

workflow = StateGraph(SupportState)

workflow.add_node("agent", support_agent_node)
workflow.add_node("tools", ToolNode([record_warranty_status]))
workflow.add_node("issue_classifier", issue_classifier_node)

workflow.add_edge(START, "agent")
workflow.add_edge("agent", "tools")
workflow.add_edge("tools", "issue_classifier")
workflow.add_edge("issue_classifier", END)

app = workflow.compile()
```

---

## Execution Lifecycle

1. **User Input:** A query enters `START` with initial state: `{"messages": [HumanMessage(...)], "warranty_status": None}`.
2. **LLM Decision:** The agent inspects `messages` and issues a `tool_call` targeting `record_warranty_status` with `{"status": "in_warranty"}`.
3. **Parameter Injection:** The graph intercepts the tool call, matches the signature, loads the active context, and initializes `ToolRuntime(tool_call_id=..., state=...)`.
4. **Command Execution:** The tool processes the status and returns `Command(update={...})`.
5. **State Ingestion:** The graph applies the updates:
   - The `ToolMessage` is matched against the LLM's `tool_call_id` and appended to `messages`.
   - `warranty_status` transitions from `None` to `"in_warranty"`.
   - `current_step` advances to `"issue_classifier"`.
6. **Continuation:** Downstream nodes immediately read the updated fields without additional payload parsing.

---

## Best Practices

- **Always Bind `tool_call_id`:** When updating `messages` inside a `Command`, ensure the `ToolMessage` receives `runtime.tool_call_id`. Omitting it causes OpenAI and Anthropic APIs to throw validation errors on subsequent requests.
- **Keep Tools Focused:** Use `Command(update={...})` only for state variables directly modified by that tool's business logic. General conversational state updates belong in dedicated routing nodes.
- **Isolate Sensitive Context:** Pass database credentials, user tokens, and internal keys through `runtime.config` rather than exposing them as prompt parameters to the LLM.

---

## The Dynamic Stage Manager (Middleware)

This function is a **dynamic stage manager** (middleware) for your AI agent.

Instead of giving the LLM one massive prompt and dozens of tools all at once, this code intercepts the AI *right before it runs*, checks what stage of the conversation you are in, and dynamically swaps out the **system prompt** and **tools** to match that exact step.

### The Big Picture: Why Do We Need This?

Think of a multi-step customer support agent. It needs to:

1. First, check warranty status (`warranty_collector`).
2. Next, identify the problem (`issue_classifier`).
3. Finally, offer a replacement or repair (`resolution_agent`).

If you give the LLM all tools and instructions at the start, it gets confused, skips steps, or tries to fix the problem before checking the warranty.

This code solves that problem by acting as a **security checkpoint and wardrobe changer** before every single LLM call.

### Step-by-Step Code Breakdown

#### 1. The Interceptor (`@wrap_model_call`)

```python
@wrap_model_call
def apply_step_config(
    request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
```

- **`@wrap_model_call`**: Tells the framework: *"Do not send the request directly to OpenAI/Anthropic yet. Run this Python function first."*
- **`request: ModelRequest`**: An object containing everything about the upcoming call—the chat history, the state variables, the current prompt, and the tools.
- **`handler`**: The actual function that sends the request to the LLM. Calling `handler(request)` means: *"I am done modifying the request; now go ahead and call the model."*

#### 2. Identifying the Current Stage

```python
current_step = request.state.get("current_step", "warranty_collector")
stage_config = STEP_CONFIG[current_step]
```

- It reads `current_step` from the agent's memory (`request.state`, which is your `SupportState` from earlier).
- If the conversation just started and `current_step` is not set yet, it defaults to `"warranty_collector"`.
- Then, it looks up that step inside a configuration dictionary (`STEP_CONFIG`) to see what rules apply to this stage.

#### 3. Safety Guardrails (`requires`)

```python
for key in stage_config["requires"]:
    if request.state.get(key) is None:
        raise ValueError(f"{key} must be set before reaching {current_step}")
```

- This prevents the agent from skipping ahead illegally.
- For example, if the current step is `"issue_classifier"`, its configuration might declare `requires: ["warranty_status"]`.
- If `warranty_status` isn't in memory yet, the code immediately halts with an error instead of letting the AI hallucinate or proceed blindly.

#### 4. Dynamic Prompt Templating

```python
system_prompt = stage_config["prompt"].format(**request.state)
```

- Each step has its own tailored prompt template.
- Python's `.format(**request.state)` fills in placeholders using the variables stored in memory:

```python
# Template in STEP_CONFIG:
"You are diagnosing an issue. Customer warranty is {warranty_status}."

# Becomes after formatting:
"You are diagnosing an issue. Customer warranty is in_warranty."
```

#### 5. Restricting Tools & Overriding the Request

```python
request = request.override(
    system_prompt=system_prompt,
    tools=stage_config["tools"],
)
return handler(request)
```

- **`request.override(...)`**: Replaces the generic prompt and tool list with the step-specific ones.
- During `warranty_collector`, the agent *only* gets the `record_warranty_status` tool.
- It does not get billing or shipping tools, so it cannot accidentally call the wrong tool.
- **`return handler(request)`**: Hands the modified request over to the LLM to generate its response.

### How This Connects to Your Earlier Tool

Notice how everything links together across turns:

```text
Turn 1:
User: "My screen is cracked, serial #123."
├── apply_step_config sees current_step = "warranty_collector"
├── Injects prompt: "Find out if device is under warranty."
├── Injects ONLY tool: [record_warranty_status]
└── LLM calls: record_warranty_status(status="in_warranty")

Turn 2:
The tool returns: Command(update={"warranty_status": "in_warranty", "current_step": "issue_classifier"})
├── apply_step_config intercepts next LLM call!
├── Reads new current_step: "issue_classifier"
├── Validates: is "warranty_status" in state? Yes ("in_warranty").
├── Injects NEW prompt: "Classify the customer's issue. Status is in_warranty."
├── Injects NEW tools: [classify_hardware_issue, search_troubleshooting_docs]
└── Passes the updated request to the LLM.
```
