import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

load_dotenv()

client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)


@tool("search")
def search_tool(query: str) -> str:
    """Search internal documentation and knowledge base."""
    print(f"\n  [TOOL EXECUTION] >>> Safe tool 'search' executed with query: '{query}'")
    return f"Search result: Documentation found matching '{query}'."


@tool("send_email")
def send_email_tool(to: str, subject: str, body: str) -> str:
    """Send an outbound email to a recipient or team."""
    print(f"\n  [TOOL EXECUTION] >>> SENSITIVE TOOL 'send_email' EXECUTING <<<")
    print(f"  [DISPATCH] Sent to: {to} | Subject: {subject}")
    return f"Email successfully sent to {to}."


@tool("delete_database")
def delete_database_tool(database_name: str) -> str:
    """Permanently delete a database or table."""
    print(f"\n  [TOOL EXECUTION] >>> DESTRUCTIVE TOOL 'delete_database' EXECUTING <<<")
    print(f"  [DATABASE DROPPED] '{database_name}' was purged.")
    return f"Database '{database_name}' was permanently deleted."


agent = create_agent(
    model=client,
    tools=[search_tool, send_email_tool, delete_database_tool],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                # Block and pause execution for sensitive tools
                "send_email": True,
                "delete_database": True,
                # Let read-only tools run automatically
                "search": False,
            }
        ),
    ],
    checkpointer=InMemorySaver(),
)


def main():
    thread_config = {"configurable": {"thread_id": "session-prod-001"}}

    print("=" * 65)
    print("🤖 HITL AGENT READY — Try queries like:")
    print(" 1. 'Search for project roadmap docs'         (Auto-approved)")
    print(" 2. 'Send an email to team@work.com about 5pm sync' (Requires approval)")
    print(" 3. 'Delete the test_users database'          (Requires approval)")
    print(" Type 'exit' to quit.")
    print("=" * 65)

    while True:
        user_input = input("\nUser > ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Shutting down session.")
            break

        print(f"\n[1/4] Sending request to agent...")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=thread_config,
        )

        current_state = agent.get_state(thread_config)

        # Loop until all pending interrupts are resolved
        while current_state.next:
            print("\n" + "!" * 65)
            print("[2/4] ⚠️  HITL MIDDLEWARE INTERCEPTED EXECUTION")

            # Extract interrupt details
            for task in current_state.tasks:
                if task.interrupts:
                    for intr in task.interrupts:
                        val = getattr(intr, "value", intr)
                        if isinstance(val, dict) and "action_requests" in val:
                            for req in val["action_requests"]:
                                print(f"  Pending Tool : {req.get('tool')}")
                                print(f"  Arguments    : {req.get('args')}")
                                print(f"  Description  : {req.get('description')}")
                        else:
                            print(f"  Interrupt details: {val}")

            print("!" * 65)

            approval = (
                input("\n[3/4] Approve this sensitive action? (y/n): ").strip().lower()
            )

            if approval in ["y", "yes"]:
                print("\n  [DECISION] Action APPROVED by user. Resuming agent...")
                decision = {"type": "approve"}
            else:
                print(
                    "\n  [DECISION] Action REJECTED by user. Resuming with rejection..."
                )
                decision = {"type": "reject"}

            # Resume execution on the exact same thread
            result = agent.invoke(
                Command(resume={"decisions": [decision]}),
                config=thread_config,
            )

            # Check if there are further chained interrupts
            current_state = agent.get_state(thread_config)

        print("\n[4/4] Final Response:")
        final_message = result["messages"][-1]
        print(getattr(final_message, "text", str(final_message.content)))


if __name__ == "__main__":
    main()
