from typing import Optional, TypedDict, Literal
from langgraph.graph import StateGraph
from openai import Client, OpenAI
from langgraph.graph import START, END

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="GEMINI_API_KEY",
)

class State(TypedDict):
    user_query: str
    llm_output: Optional[str]
    is_good: Optional[bool]

def chatbot(state: State) -> State:
    print("chatbot: ", state)
    res = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=[
            {"role": "user", "content": state["user_query"]}
        ]
    )

    state["llm_output"] = res.choices[0].message.content
    return state

def chatbot2(state: State) -> State:
    print("chatbot2: ", state)
    res = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=[
            {"role": "user", "content": state["user_query"]}
        ]
    )

    state["llm_output"] = res.choices[0].message.content
    return state

def end_node(state: State) -> State:
    print("end_node: ", state)
    return state

def evaluate_response(state: State) -> Literal["chatbot2", "end_node"]:
    print("evaluate_response: ", state)
    if input("Is the response good? (y/n)\n") == "y":
        return "end_node"
    return "chatbot2"

builder = StateGraph(State)

builder.add_node("chatbot", chatbot)
builder.add_node("chatbot2", chatbot2)
builder.add_node("end_node", end_node)

builder.add_edge(START, "chatbot")
builder.add_conditional_edges("chatbot", evaluate_response)
builder.add_edge("chatbot2", "end_node")
builder.add_edge("end_node", END)

graph = builder.compile()
result = graph.invoke(State({"user_query": "Hey, what is 2+2?"}))
print("result:", result)
