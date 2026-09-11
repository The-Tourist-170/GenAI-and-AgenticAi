from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    messages: Annotated[list, add_messages]

def chat(state: State):
    return {"messages": ["Hey there new message"]}

def sampleNode(state: State):
    return {"messages": ["messages from sample node"]}

graph_builder = StateGraph(State)
graph_builder.add_node("chat", chat)
graph_builder.add_node("sampleNode", sampleNode)

graph_builder.add_edge(START, "chat")
graph_builder.add_edge("chat", "sampleNode")
graph_builder.add_edge("sampleNode", END)

graph = graph_builder.compile()
updated_state = graph.invoke({"messages": ["Hi, my name is Ayushya"]})
print(updated_state)
