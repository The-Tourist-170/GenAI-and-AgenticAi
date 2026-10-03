import os

import dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)


@tool
def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] = [],
) -> str:
    """Send an email via email API. Requires properly formatted addresses."""
    # Stub
    return f"Email sent to {', '.join(to)} - Subject: {subject}"


EMAIL_AGENT_PROMPT = (
    "You are an email assistant. "
    "Compose professional emails based on natural language requests. "
    "Extract recipient information and craft appropriate subject lines and body text. "
    "Use send_email to send the message. "
    "Always confirm what was sent in your final response."
    "My name is Ayushya Saxena, and my email id is ayushya.saxena@example.com"
)

email_agent = create_agent(
    client,
    tools=[send_email],
    system_prompt=EMAIL_AGENT_PROMPT,
)


# --- Subagent Wrapper Tool ---
@tool
def call_email_agent(request: str) -> str:
    """Use this tool to delegate email-related tasks (drafting, sending, reminders).
    Input should be the plain English instructions for what email to write/send.
    """
    response = email_agent.invoke({"messages": [{"role": "user", "content": request}]})
    final_message = response["messages"][-1]
    return getattr(final_message, "text", str(final_message.content))


def main():
    # Local debugging run only
    print("<<-----------EMAIL AGENT TEST--------->>")
    query = "Send the design team a reminder about reviewing the new mockups"
    print(call_email_agent.invoke({"request": query}))


if __name__ == "__main__":
    main()
