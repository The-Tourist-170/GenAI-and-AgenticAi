import operator
import os
from typing import Annotated, Literal

import dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

dotenv.load_dotenv()


def log(msg: str) -> None:
    print(f"===========>> {msg}")


model = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)

r_client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)


class AgentInput(TypedDict):
    """Simple input state for each subagent."""

    query: str


class AgentOutput(TypedDict):
    """Output from each subagent."""

    source: str
    result: str


class Classification(TypedDict):
    """A single routing decision: which agent to call with what query."""

    source: Literal["notion", "github", "slack"]
    query: str


class RouterState(TypedDict):
    query: str
    classification: list[Classification]
    results: Annotated[list[AgentOutput], operator.add]
    final_answer: str


@tool
def search_code(query: str, repo: str = "main") -> str:
    """Search code in GitHub repositories."""
    log(f"TOOL search_code called: query={query!r} repo={repo!r}")
    return f"Found code matching '{query}' in {repo}: authentication middleware in src/auth.py"


@tool
def search_issues(query: str) -> str:
    """Search GitHub issues and pull requests."""
    log(f"TOOL search_issues called: query={query!r}")
    return f"Found 3 issues matching '{query}': #142 (API auth docs), #89 (OAuth flow), #203 (token refresh)"


@tool
def search_prs(query: str) -> str:
    """Search pull requests for implementation details."""
    log(f"TOOL search_prs called: query={query!r}")
    return f"PR #156 added JWT authentication, PR #178 updated OAuth scopes"


@tool
def search_notion(query: str) -> str:
    """Search Notion workspace for documentation."""
    log(f"TOOL search_notion called: query={query!r}")
    return f"Found documentation: 'API Authentication Guide' - covers OAuth2 flow, API keys, and JWT tokens"


@tool
def get_page(page_id: str) -> str:
    """Get a specific Notion page by ID."""
    log(f"TOOL get_page called: page_id={page_id!r}")
    return f"Page content: Step-by-step authentication setup instructions"


@tool
def search_slack(query: str) -> str:
    """Search Slack messages and threads."""
    log(f"TOOL search_slack called: query={query!r}")
    return f"Found discussion in #engineering: 'Use Bearer tokens for API auth, see docs for refresh flow'"


@tool
def get_thread(thread_id: str) -> str:
    """Get a specific Slack thread."""
    log(f"TOOL get_thread called: thread_id={thread_id!r}")
    return f"Thread discusses best practices for API key rotation"


github_agent = create_agent(
    model,
    tools=[search_code, search_issues, search_prs],
    system_prompt=(
        "You are a GitHub expert. Answer questions about code, "
        "API references, and implementation details by searching "
        "repositories, issues, and pull requests."
    ),
)

notion_agent = create_agent(
    model,
    tools=[search_notion, get_page],
    system_prompt=(
        "You are a Notion expert. Answer questions about internal "
        "processes, policies, and team documentation by searching "
        "the organization's Notion workspace."
    ),
)

slack_agent = create_agent(
    model,
    tools=[search_slack, get_thread],
    system_prompt=(
        "You are a Slack expert. Answer questions by searching "
        "relevant threads and discussions where team members have "
        "shared knowledge and solutions."
    ),
)

log("subagents created: github_agent, notion_agent, slack_agent")


class ClassificationResult(BaseModel):
    """Result of classifying a user query into agent-specific sub-questions."""

    classification: list[Classification] = Field(
        description="List of agents to invoke with their targeted sub-questions"
    )


def classify_query(state: RouterState) -> dict:
    """Classify query and determine which agents to invoke."""
    log("NODE 'classify' entered")
    log(f"  query = {state['query']!r}")

    structured_llm = r_client.with_structured_output(
        ClassificationResult, method="json_mode"
    )

    log("  calling LLM (with_structured_output, method=json_mode) to classify query")
    res = structured_llm.invoke(
        [
            {
                "role": "system",
                "content": """Analyze this query and determine which knowledge bases to consult.
       For each relevant source, generate a targeted sub-question optimized for that source.

       Available sources:
       - github: Code, API references, implementation details, issues, pull requests
       - notion: Internal documentation, processes, policies, team wikis
       - slack: Team discussions, informal knowledge sharing, recent conversations

       Return ONLY the sources that are relevant to the query. Each source should have
       a targeted sub-question optimized for that specific knowledge domain.

       Respond with ONLY a valid JSON object. No prose, no markdown, no bullet lists.
       The JSON must match this exact shape:

       {
         "classification": [
           {"source": "github", "query": "targeted sub-question"},
           {"source": "notion", "query": "targeted sub-question"}
         ]
       }

       Example for "How do I authenticate API requests?":
       {
         "classification": [
           {"source": "github", "query": "What authentication code exists? Search for auth middleware, JWT handling"},
           {"source": "notion", "query": "What authentication documentation exists? Look for API auth guides"}
         ]
       }
       (slack omitted because it's not relevant for this technical question)""",
            },
            {"role": "user", "content": state["query"]},
        ]
    )

    log(f"  classifier returned {len(res.classification)} source(s): "
        f"{[c['source'] for c in res.classification]}")

    if not res.classification:
        log("  classifier returned no sources -> falling back to ALL sources")
        classification = [
            {"source": "github", "query": state["query"]},
            {"source": "notion", "query": state["query"]},
            {"source": "slack", "query": state["query"]},
        ]
    else:
        classification = res.classification

    log("NODE 'classify' finished")
    return {"classification": classification}


def route_to_agents(state: RouterState) -> list[Send]:
    """Fan out to agents based on classifications."""
    targets = [c["source"] for c in state["classification"]]
    log(f"route_to_agents: fanning out to {targets}")
    return [Send(c["source"], {"query": c["query"]}) for c in state["classification"]]


def query_github(state: AgentInput) -> dict:
    """Query the GitHub agent."""
    log(f"NODE 'github' entered: query={state['query']!r}")
    log("  invoking github_agent (LLM) ...")
    result = github_agent.invoke(
        {"messages": [{"role": "user", "content": state["query"]}]}
    )
    content = result["messages"][-1].content
    log(f"  github_agent returned {len(content)} chars")
    return {"results": [{"source": "github", "result": content}]}


def query_notion(state: AgentInput) -> dict:
    """Query the Notion agent."""
    log(f"NODE 'notion' entered: query={state['query']!r}")
    log("  invoking notion_agent (LLM) ...")
    result = notion_agent.invoke(
        {"messages": [{"role": "user", "content": state["query"]}]}
    )
    content = result["messages"][-1].content
    log(f"  notion_agent returned {len(content)} chars")
    return {"results": [{"source": "notion", "result": content}]}


def query_slack(state: AgentInput) -> dict:
    """Query the Slack agent."""
    log(f"NODE 'slack' entered: query={state['query']!r}")
    log("  invoking slack_agent (LLM) ...")
    result = slack_agent.invoke(
        {"messages": [{"role": "user", "content": state["query"]}]}
    )
    content = result["messages"][-1].content
    log(f"  slack_agent returned {len(content)} chars")
    return {"results": [{"source": "slack", "result": content}]}


def synthesize_results(state: RouterState) -> dict:
    """Combine results from all agents into a coherent answer."""
    log("NODE 'synthesize' entered")
    results = state.get("results") or []
    log(f"  collected {len(results)} result(s) from fan-in")

    if not results:
        log("  no results -> returning fallback answer")
        return {"final_answer": "No results found from any knowledge source."}

    # Format results for synthesis
    formatted = [
        f"**From {r['source'].title()}:**\n{r['result']}" for r in results
    ]

    log("  calling LLM (r_client) to synthesize results")
    synthesis_response = r_client.invoke(
        [
            {
                "role": "system",
                "content": f"""Synthesize these search results to answer the original question: "{state["query"]}"

- Combine information from multiple sources without redundancy
- Highlight the most relevant and actionable information
- Note any discrepancies between sources
- Keep the response concise and well-organized""",
            },
            {"role": "user", "content": "\n\n".join(formatted)},
        ]
    )

    log(f"  synthesis finished: {len(synthesis_response.content)} chars")
    return {"final_answer": synthesis_response.content}


workflow = (
    StateGraph(RouterState)
    .add_node("classify", classify_query)
    .add_node("github", query_github)
    .add_node("notion", query_notion)
    .add_node("slack", query_slack)
    .add_node("synthesize", synthesize_results)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route_to_agents, ["github", "notion", "slack"])
    .add_edge("github", "synthesize")
    .add_edge("notion", "synthesize")
    .add_edge("slack", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)

log("router workflow compiled: classify -> github/notion/slack -> synthesize")


@tool
def search_knowledge_base(query: str) -> str:
    """Search across multiple knowledge sources (GitHub, Notion, Slack).

    Use this to find information about code, documentation, or team discussions.
    """
    log(f"TOOL search_knowledge_base called: query={query!r}")
    log("  invoking router workflow ...")
    result = workflow.invoke({"query": query})
    final_answer = result.get("final_answer") or "The knowledge search produced no answer."
    log(f"  router workflow returned final_answer ({len(final_answer)} chars)")
    return final_answer


conversational_agent = create_agent(
    model,
    tools=[search_knowledge_base],
    system_prompt=(
        "You are a helpful assistant that answers questions about our organization. "
        "Use the search_knowledge_base tool to find information across our code, "
        "documentation, and team discussions."
    ),
    checkpointer=InMemorySaver(),
)

log("conversational_agent created with tool: search_knowledge_base")


def main():
    config = {"configurable": {"thread_id": "user-123"}}

    log("main: invoking conversational_agent ...")
    result = conversational_agent.invoke(
        {
            "messages": [
                {"role": "user", "content": "How do I authenticate API requests?"}
            ]
        },
        config,
    )
    final_content = result["messages"][-1].content
    log(f"main: conversational_agent finished ({len(final_content)} chars)")
    print(final_content)


if __name__ == "__main__":
    main()
