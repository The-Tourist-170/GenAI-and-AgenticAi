import operator
from typing import Annotated, Optional, TypedDict
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, START, StateGraph
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="GEMINI_API_KEY",
)

# 1. Use Annotated with operator.add so new messages are appended to history
class State(TypedDict):
    messages: Annotated[list[dict], operator.add]

def chatbot(state: State) -> dict:
    # 2. Pass the full accumulated message list to the model
    res = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=state["messages"],
    )

    assistant_reply = {
        "role": "assistant",
        "content": res.choices[0].message.content,
    }
    
    # Return only the new message; operator.add appends it to state["messages"]
    return {"messages": [assistant_reply]}

builder = StateGraph(State)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)

DB_URI = "mongodb://admin:password@localhost:27017"

with MongoDBSaver.from_conn_string(DB_URI) as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)

    # A thread_id is simply a conversation label (like a chat's unique name or session ID) that tells the database exactly which user's memory to open, update, or save. LangGraph cannot handle this automatically because web servers are stateless—your app needs to decide whether an incoming message is a continuation of an ongoing chat (using an existing thread_id) or the start of a brand-new conversation (using a new thread_id), allowing different users and past conversations to stay completely separate without getting mixed up.
    config = {"configurable": {"thread_id": "Chandler"}}

    # First turn
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "My name is Chandler."}]},
        config,
    )
    # ------------------------>> Uncomment to test the second turn and comment out the first turn
    # # Second turn
    # result = graph.invoke(
    #     {"messages": [{"role": "user", "content": "What is my name?"}]},
    #     config,
    # )

    print("Last assistant reply:", result["messages"][-1]["content"])
