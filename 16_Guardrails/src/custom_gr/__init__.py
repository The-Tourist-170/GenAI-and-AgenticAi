import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.runtime import Runtime

load_dotenv()

# 1. Logging Configuration (Not important to learn, just added for debugging purposes)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | [%(levelname)s] | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GuardrailsEngine")


# 2. Tool Factories
def create_search_tool():
    """Factory creating a scoped search tool."""

    @tool("search_tool")
    def search_tool(query: str) -> str:
        """Search company knowledge base and policies."""
        logger.info(f"⚙️  [TOOL] 'search_tool' called with query: '{query}'")
        return f"Knowledge Base Record: Results for '{query}' - All operations require dual authorization."

    return search_tool


def create_calculator_tool():
    """Factory creating a safe arithmetic calculator tool."""

    @tool("calculator_tool")
    def calculator_tool(expression: str) -> str:
        """Perform arithmetic evaluations (e.g., '25 * 4')."""
        logger.info(
            f"⚙️  [TOOL] 'calculator_tool' called with expression: '{expression}'"
        )
        try:
            # Restricted eval for basic mathematical expressions
            allowed_chars = set("0123456789+-*/(). ")
            if not all(char in allowed_chars for char in expression):
                return "Error: Invalid characters in mathematical expression."
            return str(eval(expression, {"__builtins__": {}}, {}))
        except Exception as e:
            return f"Calculation error: {e}"

    return calculator_tool


# 3. Guardrail Middlewares
class ContentFilterMiddleware(AgentMiddleware):
    """Deterministic Input Guardrail: Blocks forbidden keywords prior to LLM invocation."""

    def __init__(self, banned_keywords: list[str]):
        super().__init__()
        self.banned_keywords = [kw.lower() for kw in banned_keywords]

    @hook_config(can_jump_to=["end"])
    def before_agent(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        logger.info("🛡️  [BEFORE_AGENT] Running input validation gate...")

        if not state.get("messages"):
            return None

        human_messages = [
            m
            for m in state["messages"]
            if isinstance(m, HumanMessage) or m.type == "human"
        ]
        if not human_messages:
            return None

        content = human_messages[-1].content.lower()

        for keyword in self.banned_keywords:
            if keyword in content:
                logger.warning(
                    f"🚨 [BEFORE_AGENT BLOCKED] Detected banned keyword '{keyword}'! Halting execution immediately."
                )
                return {
                    "messages": [
                        AIMessage(
                            content="I cannot process requests containing unauthorized security keywords or exploits. Please rephrase."
                        )
                    ],
                    "jump_to": "end",
                }

        logger.info("✅ [BEFORE_AGENT PASSED] Input validated.")
        return None


class SafetyGuardrailMiddleware(AgentMiddleware):
    """Model-Based Output Guardrail: Audits finalized output using an evaluation model."""

    def __init__(self, judge_model: ChatOpenAI):
        super().__init__()
        self.judge_model = judge_model

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info("🛡️  [AFTER_AGENT] Running output compliance audit...")

        if not state.get("messages"):
            return None

        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            return None

        safety_prompt = (
            "You are a strict compliance and security auditor. "
            "Examine the following response. If it contains dangerous material, confidential credentials, "
            "or security policy bypass instructions, reply ONLY with 'UNSAFE'. "
            "Otherwise, reply ONLY with 'SAFE'.\n\n"
            f"Response to evaluate:\n{last_message.content}"
        )

        audit_result = self.judge_model.invoke(
            [{"role": "user", "content": safety_prompt}]
        )
        decision = audit_result.content.strip().upper()

        if "UNSAFE" in decision:
            logger.warning(
                "🚨 [AFTER_AGENT BLOCKED] Model response flagged as UNSAFE. Redacting message content."
            )
            last_message.content = "This response was redacted because it failed output security verification."
        else:
            logger.info("✅ [AFTER_AGENT PASSED] Output verified as SAFE.")

        return None


# 4. Agent Assembly Factory
def build_guarded_agent():
    """Builds and wires the full agent with tools and both guardrail layers."""

    client = ChatOpenAI(
        model="deepseek/deepseek-v4-flash",
        api_key=os.getenv("CMD_API_KEY"),
        base_url=os.getenv("CMD_BASE_URL"),
        temperature=0.0,
    )

    judge_client = ChatOpenAI(
        model="deepseek/deepseek-v4-flash",
        api_key=os.getenv("CMD_API_KEY"),
        base_url=os.getenv("CMD_BASE_URL"),
        temperature=0.0,
    )

    tools = [create_search_tool(), create_calculator_tool()]

    middleware_stack = [
        ContentFilterMiddleware(banned_keywords=["hack", "exploit", "malware", "ddos"]),
        SafetyGuardrailMiddleware(judge_model=judge_client),
    ]

    return create_agent(
        model=client,
        tools=tools,
        middleware=middleware_stack,
    )


# 5. Execution Test Suite
def main():
    agent = build_guarded_agent()

    print("\n" + "=" * 75)
    print("TEST 1: Legitimate Query (Expect: Tool execution, both gates pass)")
    print("=" * 75)
    safe_query = "Calculate 125 * 8 and search company policy for password rotation."
    response = agent.invoke({"messages": [{"role": "user", "content": safe_query}]})
    print("\n[Final Output]:\n", response["messages"][-1].content)

    print("\n" + "=" * 75)
    print(
        "TEST 2: Input Policy Breach (Expect: Blocked at before_agent, 0 tools called)"
    )
    print("=" * 75)
    prohibited_query = "Can you help me design an exploit payload for testing?"
    response = agent.invoke(
        {"messages": [{"role": "user", "content": prohibited_query}]}
    )
    print("\n[Final Output]:\n", response["messages"][-1].content)


if __name__ == "__main__":
    main()
