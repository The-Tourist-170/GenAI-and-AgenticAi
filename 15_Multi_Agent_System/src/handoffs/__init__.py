import os
import uuid
from typing import Callable, Literal

import dotenv
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from typing_extensions import NotRequired

dotenv.load_dotenv()

prompts = {
    "WARRANTY_COLLECTOR_PROMPT": """You are a customer support agent helping with device issues.

CURRENT STAGE: Warranty verification

At this step, you need to:
1. Greet the customer warmly
2. Ask if their device is under warranty
3. Use record_warranty_status to record their response and move to the next step

Be conversational and friendly. Don't ask multiple questions at once.""",
    "ISSUE_CLASSIFIER_PROMPT": """You are a customer support agent helping with device issues.

CURRENT STAGE: Issue classification
CUSTOMER INFO: Warranty status is {warranty_status}

At this step, you need to:
1. Ask the customer to describe their issue
2. Determine if it's a hardware issue (physical damage, broken parts) or software issue (app crashes, performance)
3. Use record_issue_type to record the classification and move to the next step

If unclear, ask clarifying questions before classifying.""",
    "RESOLUTION_SPECIALIST_PROMPT": """You are a customer support agent helping with device issues.

CURRENT STAGE: Resolution
CUSTOMER INFO: Warranty status is {warranty_status}, issue type is {issue_type}

At this step, you need to:
1. For SOFTWARE issues: provide troubleshooting steps using provide_solution
2. For HARDWARE issues:
   - If IN WARRANTY: explain warranty repair process using provide_solution
   - If OUT OF WARRANTY: escalate_to_human for paid repair options

Be specific and helpful in your solutions.""",
}

client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)

SupportStep = Literal["warranty_collector", "issue_classifier", "resolution_specialist"]


class SupportState(AgentState):
    """State for customer support workflow."""

    current_step: NotRequired[SupportStep]
    warranty_status: NotRequired[Literal["in_warranty", "out_of_warranty"]]
    issue_type: NotRequired[Literal["hardware", "software"]]


@tool
def record_warranty_status(
    status: Literal["in_warranty", "out_of_warranty"],
    runtime: ToolRuntime[None, SupportState],
) -> Command:
    """Record the customer's warranty status and transition to issue classification."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Warranty status recorded: {status}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "warranty_status": status,
            "current_step": "issue_classifier",
        }
    )


@tool
def record_issue_type(
    issue_type: Literal["hardware", "software"],
    runtime: ToolRuntime[None, SupportState],
) -> Command:
    """Record the customer's issue type and transition to resolution specialist."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Issue type recorded: {issue_type}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "issue_type": issue_type,
            "current_step": "resolution_specialist",
        }
    )


@tool
def escalate_to_human(reason: str) -> str:
    """Escalate the case to a human support specialist."""
    # In a real system, this would create a ticket, notify staff, etc.
    return f"Escalating to human support. Reason: {reason}"


@tool
def provide_solution(solution: str) -> str:
    """Provide a solution to the customer's issue."""
    return f"Solution provided: {solution}"


STEP_CONFIG = {
    "warranty_collector": {
        "prompt": prompts["WARRANTY_COLLECTOR_PROMPT"],
        "tools": [record_warranty_status],
        "requires": [],
    },
    "issue_classifier": {
        "prompt": prompts["ISSUE_CLASSIFIER_PROMPT"],
        "tools": [record_issue_type],
        "requires": ["warranty_status"],
    },
    "resolution_specialist": {
        "prompt": prompts["RESOLUTION_SPECIALIST_PROMPT"],
        "tools": [provide_solution, escalate_to_human],
        "requires": ["warranty_status", "issue_type"],
    },
}


@wrap_model_call
def apply_step_config(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Configure agent behavior based on the current step."""
    current_step = request.state.get("current_step", "warranty_collector")

    stage_config = STEP_CONFIG[current_step]

    for key in stage_config["requires"]:
        if request.state.get(key) is None:
            raise ValueError(f"{key} must be set before reaching {current_step}")

    system_prompt = stage_config["prompt"].format(**request.state)

    request = request.override(
        system_prompt=system_prompt,
        tools=stage_config["tools"],
    )

    return handler(request)


all_tools = [
    record_warranty_status,
    record_issue_type,
    provide_solution,
    escalate_to_human,
]

# Why a checkpointer? The checkpointer maintains state across conversation turns. Without it, the current_step state would be lost between user messages, breaking the workflow.
agent = create_agent(
    client,
    tools=all_tools,
    state_schema=SupportState,
    middleware=[apply_step_config],
    checkpointer=InMemorySaver(),
)


def main():
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # --- Turn 1: Warranty Collection ---
    print("=== Turn 1: Warranty Collection ===")
    result = agent.invoke(
        {"messages": [("user", "Hi, my phone screen is cracked")]},
        config,
    )
    print("Agent:", result["messages"][-1].content)

    # --- Turn 2: User responds about warranty ---
    print("\n=== Turn 2: Warranty Response ===")
    result = agent.invoke(
        {"messages": [("user", "Yes, it's still under warranty")]},
        config,
    )
    print("Agent:", result["messages"][-1].content)
    print(f"Current step: {result.get('current_step')}")

    # --- Turn 3: User describes the issue ---
    print("\n=== Turn 3: Issue Description ===")
    result = agent.invoke(
        {"messages": [("user", "The screen is physically cracked from dropping it")]},
        config,
    )
    print("Agent:", result["messages"][-1].content)
    print(f"Current step: {result.get('current_step')}")

    # --- Turn 4: Resolution ---
    print("\n=== Turn 4: Resolution ===")
    result = agent.invoke(
        {"messages": [("user", "What should I do?")]},
        config,
    )
    print("Agent:", result["messages"][-1].content)
