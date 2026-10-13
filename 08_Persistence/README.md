# 08 — Persistence

## What this is about

Module 07's graph had one fatal flaw: **the state lived in RAM.** Run the script, chat twice, and
it remembers — kill the process and every conversation is gone. A real assistant must survive
restarts, crashes, and days between messages.

**Think of a video game.** You don't leave the console running for a week — you **save**. This
module adds exactly that to the graph:

- **Checkpointing** = saving the game after every move.
- **`thread_id`** = the save slot's name.
- **MongoDB** = the memory card the saves live on.

Kill the process, come back tomorrow, load the slot — the conversation resumes exactly where it
left off, history intact.

## What you need

```bash
pip install langgraph langgraph-checkpoint-mongodb openai
```

`langgraph-checkpoint-mongodb` is the package that provides `MongoDBSaver` — it's not pulled in by
base langgraph, so install it explicitly. (Plus Docker, for the database itself.) Or
`pip install -r requirements.txt` from the repo root.

---

## The reducer, second flavor

Module 07 used `add_messages`. This module does the same job with a different tool — worth seeing
both:

```python
class State(TypedDict):
    messages: Annotated[list[dict], operator.add]
```

- **Module 07 — `add_messages`**: built for LangChain message *objects*; appends, assigns IDs, and
  handles LangChain's message types.
- **This module — `operator.add`**: plain list concatenation. The messages here are raw dicts in
  OpenAI format (`{"role": ..., "content": ...}`), so the simplest reducer is the right one.

Both say the same thing to LangGraph: *"when a node returns a list for this key, append it — don't
overwrite."*

## The code, piece by piece

### The node — full history in, one message out

```python
def chatbot(state: State) -> dict:
    res = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=state["messages"],      # the ENTIRE accumulated history
    )
    assistant_reply = {"role": "assistant", "content": res.choices[0].message.content}
    return {"messages": [assistant_reply]}   # only the NEW message
```

The pattern from module 07, now doing real work: the node reads the whole history (so the model
has context) but returns **only its update** — and `operator.add` appends it. The graph, not the
node, is responsible for accumulation.

### The save system — three lines

```python
DB_URI = "mongodb://admin:password@localhost:27017"

with MongoDBSaver.from_conn_string(DB_URI) as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
```

`MongoDBSaver` is a **checkpointer** — LangGraph's name for the thing that saves and loads state.
Hand it to `compile()` and the graph becomes persistent: after *every step* of *every run*, the
full state is serialized into MongoDB. The `admin:password` in the URI must match the credentials
the Docker container was started with (below).

### The save slot

```python
config = {"configurable": {"thread_id": "Chandler"}}
result = graph.invoke(
    {"messages": [{"role": "user", "content": "My name is Chandler."}]},
    config,
)
```

Two things to notice:

1. **`thread_id`** — this is which save slot to use. Every `invoke` carries it, so one database
   can hold thousands of separate conversations that never bleed into each other. In a real app
   it would come from the session: one thread per user chat.
2. **The input is only the new message.** No history is resent — the checkpointer loads what's
   under `"Chandler"`, merges your one new message into it, and *that* is what the node receives.

### The two-turn experiment

The script's second half is commented out on purpose:

```python
# result = graph.invoke(
#     {"messages": [{"role": "user", "content": "What is my name?"}]},
#     config,
# )
```

To see persistence with your own eyes: run the script once (turn one), **kill the process**, then
swap the comments and run again. The model answers *"You're Chandler"* — from a process that has
never met you.

```mermaid
flowchart TD
    subgraph run1["first run"]
        A1["invoke: 'My name is Chandler.'"] --> G1["chatbot sees 1 message"]
        G1 --> CP1["checkpointer saves state<br/>thread_id = Chandler"]
    end
    subgraph run2["process killed — run again later"]
        A2["invoke: 'What is my name?'"] --> CP2["checkpointer loads the save"]
        CP2 --> G2["chatbot sees BOTH messages"]
        G2 --> ANS["'You're Chandler.'"]
    end
    CP1 -.->|"MongoDB holds the save"| CP2

    linkStyle 0,1,2,3,4,5 stroke:#4f7cff,stroke-width:2px;
```

---

## Docker, round three — environment and volumes

```yaml
services:
  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=password
    volumes:
      - mongo_data:/data/db
volumes:
  mongo_data:
```

Two new Compose features, both doing real work:

- **`environment:`** — sets the Mongo root username and password on first boot. This is why the
  code's connection string is `mongodb://admin:password@...` — the two files must agree.
- **`volumes:`** — the important one. A container is disposable by design; delete it and its
  filesystem dies with it. A **named volume** (`mongo_data`) is storage that lives *outside* the
  container, mounted at `/data/db` inside it. Container dies → volume survives → your saved
  conversations are still there.

```mermaid
flowchart LR
    M["mongo container<br/>(disposable)"] -->|"writes to"| V[("mongo_data volume<br/>survives restarts")]

    linkStyle 0 stroke:#4f7cff,stroke-width:2px;
```

Which is the whole theme of this module: **the app persists via checkpoints, the database
persists via volumes.** You can now kill *either* layer and lose nothing.

## Run it

```bash
docker compose up -d     # Mongo on :27017, with a durable volume
python chat.py           # turn one: introduce yourself
# ...kill it, swap the comment block, run again...
python chat.py           # turn two: "What is my name?" → Chandler
```

Each run re-indexes nothing, re-chats nothing — the graph just loads its save and continues.

## Key takeaways

- **A checkpointer turns a graph into a resumable one**: state is saved after every step, keyed by
  `thread_id`.
- **`thread_id` is the save slot** — one database, many independent conversations. Your app
  decides which slot an incoming message belongs to.
- With a checkpointer, you **send only the new message**; history comes back from the database.
- `operator.add` and `add_messages` are the same idea for different data: **reducers define how
  updates merge**.
- Docker named volumes give the database the same durability the graph just gained.
- This is short-term memory: raw history, replayed verbatim. Deciding *what's worth remembering*
  is the next module.
