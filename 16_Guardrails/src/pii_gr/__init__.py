import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import PIIMiddleware
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()

client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)


@tool
def customer_service_tool(query: str, account_id: str = "guest") -> str:
    """Process a customer service inquiry, billing update, or support ticket.

    Args:
        query: The user's issue or request description.
        account_id: The customer's account identifier (optional).
    """
    print(f"\n[TOOL EXECUTION] Received query parameter:\n>>> {query}\n")
    return f"Support ticket created for account '{account_id}'. Ingestion log: {query}"


@tool
def email_tool(to: str, subject: str, body: str) -> str:
    """Send an email notification or confirmation to a recipient.

    Args:
        to: The recipient's email address.
        subject: The subject line of the email.
        body: The text content of the message.
    """
    print(
        f"\n[TOOL EXECUTION] Received email parameters:\n>>> {to}\n>>> {subject}\n>>> {body}\n"
    )
    return f"Email successfully dispatched to {to} [Subject: {subject}]."


agent = create_agent(
    model=client,
    tools=[customer_service_tool, email_tool],
    middleware=[
        # Replaces raw email with [REDACTED_EMAIL] before sending to the LLM
        PIIMiddleware(
            "email",
            strategy="redact",
            apply_to_input=True,
        ),
        # Masks credit card numbers, showing only the last 4 digits
        PIIMiddleware(
            "credit_card",
            strategy="mask",
            apply_to_input=True,
        ),
        # Hard stop: raises an exception immediately if a private API key is leaked
        PIIMiddleware(
            "api_key",
            detector=r"sk-[a-zA-Z0-9]{32}",
            strategy="hash",
            apply_to_input=True,
        ),
    ],
)


def main():
    print("<<----------- RUNNING PII GUARDRAIL TEST ----------->>")

    user_prompt = """Hello, my email is john.doe@example.com and my card number
        is 5105-1051-0510-5100. My secret key is
        sk-1234567890abcdef1234567890abcdef.
        Please log this support request."""

    result = agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})

    print("\n--- Original Input (What you typed) ---")
    print(user_prompt)

    print("\n--- Message 0 in State (What the LLM actually received) ---")
    print(result["messages"][0].content)

    print("\nFinal Output:\n", result["messages"][-1].content)


if __name__ == "__main__":
    main()
