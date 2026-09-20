# Weather MCP Server

A Model Context Protocol (MCP) server that exposes live weather data to any MCP-capable
AI client (Claude Desktop, the MCP Inspector, etc.). Ask the client for the weather in a
city and it calls the `weather` tool in this server, which fetches real data from
[wttr.in](https://wttr.in).

Built with the **MCP Python SDK** (`mcp==2.2.0`) and managed with **uv**.

---

## Table of Contents

- [What is MCP?](#what-is-mcp)
  - [The problem it solves](#the-problem-it-solves)
  - [Architecture: host, client, server](#architecture-host-client-server)
  - [The protocol](#the-protocol)
  - [Server primitives: tools, resources, prompts](#server-primitives-tools-resources-prompts)
  - [Transports](#transports)
  - [Lifecycle](#lifecycle)
- [How this project is structured](#how-this-project-is-structured)
- [What is `uv`, and why not `pip`?](#what-is-uv-and-why-not-pip)
- [Project layout](#project-layout)
- [How to run the server](#how-to-run-the-server)
  - [Prerequisites](#prerequisites)
  - [Run it (script entry point)](#run-it-script-entry-point)
  - [Run it in the MCP Inspector](#run-it-in-the-mcp-inspector)
  - [Run it as a module](#run-it-as-a-module)
  - [Connect a client](#connect-a-client)
- [How to build your own MCP server](#how-to-build-your-own-mcp-server)
- [Troubleshooting](#troubleshooting)

---

## What is MCP?

**MCP (Model Context Protocol)** is an open standard that lets AI applications talk to
external tools and data sources through one uniform interface. Think of it as **USB-C for
AI integrations**: instead of every AI app writing custom glue for every tool, both sides
speak one protocol, and anything built to the protocol plugs into anything else.

### The problem it solves

Before MCP, wiring `N` AI apps to `M` tools required up to `N × M` bespoke integrations.
Every host had its own function-calling format, auth, and transport. MCP collapses that
into `N + M`: each host implements the protocol once, each tool/server implements it once,
and they interoperate.

```
   Without MCP:  N × M integrations          With MCP:  N + M integrations
   ┌──────┐ ┌──────┐                         ┌──────┐        ┌────────┐
   │ Host │ │ Host │  ...                     │ Host │        │ Server │
   └──┬───┘ └──┬───┘                         └──┬───┘        └───┬────┘
      │        │        ┌────────┐              │  MCP           │
      ├────────┼────────┤ Tool A │              └───────┬────────┘
      ├────────┼────────┤ Tool B │                   ┌──┴───┐
      └────────┴────────┤ Tool C │                   │ Host │  (N + M)
                       └────────┘                    └──────┘
```

### Architecture: host, client, server

MCP is a **client–server** protocol. Three roles are involved:

| Role | What it is | Example |
| --- | --- | --- |
| **Host** | The AI application the user interacts with. It decides *when* to call a tool and feeds results back to the model. | Claude Desktop, an IDE, a custom agent |
| **Client** | A connector **inside** the host, one per server. It owns the 1:1 connection and speaks the protocol. | The host's MCP connector |
| **Server** | The program that exposes capabilities (tools, resources, prompts). This repo **is** a server. | `weather-mcp` |

```
┌──────────────────────── Host (e.g. Claude Desktop) ────────────────────────┐
│                                                                             │
│   ┌──────────────┐   ┌──────────────┐                                       │
│   │ MCP Client 1 │   │ MCP Client 2 │   ... the LLM plans & the host routes │
│   └──────┬───────┘   └──────┬───────┘                                       │
└──────────┼──────────────────┼───────────────────────────────────────────────┘
           │  MCP (JSON-RPC 2.0)                 │
           │  e.g. stdio                          │
    ┌──────▼───────────┐                  ┌───────▼──────────┐
    │ Server: weather  │                  │ Server: files    │
    │  • tool: weather │                  │  • tool: read…   │
    └──────────────────┘                  └──────────────────┘
```

Key point: **the server does not contain the LLM**. It just describes and executes
capabilities. The host/model does the reasoning and decides which tool to call.

### The protocol

MCP is built on **JSON-RPC 2.0**. Every interaction is a request/response or notification
with a method name and JSON params. For example, when a client wants to know what this
server can do, it sends:

```json
{ "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {} }
```

and the `weather-mcp` server answers with the tool it exposes:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "weather",
        "description": "Get weather for a city.\n\n    Args:\n        city: ...",
        "inputSchema": {
          "properties": { "city": { "type": "string" } },
          "required": ["city"],
          "type": "object"
        }
      }
    ]
  }
}
```

The client then calls it with `tools/call` and params `{"name": "weather", "arguments": {"city": "Mumbai"}}`.

### Server primitives: tools, resources, prompts

An MCP server can expose three kinds of capability:

| Primitive | Controlled by | Purpose | In this repo |
| --- | --- | --- | --- |
| **Tools** | The **model** | Functions the model can invoke (side effects, computations). | `weather` ✅ |
| **Resources** | The **application** | Read-only data (files, records) the host can load into context. | — |
| **Prompts** | The **user** | Reusable prompt templates/workflows surfaced in the UI. | — |

This server implements one **tool**, which is the most common primitive for "give the
model a new ability".

### Transports

The transport is *how* messages travel between client and server:

| Transport | Use case |
| --- | --- |
| **`stdio`** | Local servers. The host spawns the server as a child process and talks over stdin/stdout. **This is what this repo uses.** |
| **`sse`** | Legacy HTTP transport (Server-Sent Events). |
| **`streamable-http`** | Modern HTTP transport for remote/multi-client servers. |

### Lifecycle

Every session follows the same handshake before any work happens:

1. **`initialize`** — the client announces its protocol version and capabilities; the
   server replies with its own (name, version, capabilities).
2. **`notifications/initialized`** — the client confirms; the session is live.
3. **Requests** — `tools/list`, `tools/call`, `resources/read`, `prompts/get`, …
4. **Shutdown** — the connection closes (or the process exits).

---

## How this project is structured

Everything lives in one small, readable module: `src/weather_mcp/server.py`.

```
                      ┌──────────────────────────────────────────────┐
                      │  MCP client (Inspector / Claude Desktop)     │
                      └───────────────────┬──────────────────────────┘
                                          │  JSON-RPC 2.0 over stdio
                                          ▼
        ┌───────────────────────────────────────────────────────────────┐
        │  src/weather_mcp/server.py                                    │
        │                                                               │
        │  mcp = MCPServer("weather")        ← the server object        │
        │                                                               │
        │  @mcp.tool()                                                  │
        │  async def weather(city: str):     ← capability exposed       │
        │        return await get_weather(city)                         │
        │                          │                                    │
        │                          ▼                                    │
        │  async def get_weather(city)  ──httpx──▶  https://wttr.in     │
        │                                                               │
        │  def main(): mcp.run(transport="stdio")   ← entry point       │
        └───────────────────────────────────────────────────────────────┘
```

Two layers, deliberately separated:

- **`weather`** (the tool) — protocol-facing. Its name, arguments, and docstring are what
  the model sees; the SDK derives the JSON Schema from the type hints.
- **`get_weather`** (the logic) — a plain async function that hits the upstream API. It has
  no MCP knowledge, so it stays testable and reusable.

The `pyproject.toml` wires it together and declares the console script:

```toml
[project.scripts]
weather-mcp = "weather_mcp.server:main"
```

> **Note:** `pyproject.toml` also declares a `weather-client` script pointing at
> `weather_mcp.client:main`, but that module does not exist in this repo yet — only the
> server is implemented.

---

## What is `uv`, and why not `pip`?

**`uv`** is a single, extremely fast Python project and package manager (written in Rust by
Astral, the makers of `ruff`). It replaces the tangle of `pip` + `venv` + `pip-tools` +
`pipx` + `virtualenv` with **one tool and one file**.

### Why this project uses `uv` instead of `pip`

| Concern | `pip` + `venv` | `uv` |
| --- | --- | --- |
| **Speed** | Resolves/installs sequentially; slow. | Parallel + globally cached. Orders of magnitude faster. |
| **Lockfile** | None built in (`requirements.txt` is just a snapshot). | `uv.lock` — fully resolved, hash-pinned, reproducible. |
| **Source of truth** | You hand-maintain `requirements.txt`. | You declare deps in `pyproject.toml`; the lock is generated. |
| **Virtualenv** | You create/activate it manually. | `uv run` manages `.venv` for you automatically. |
| **Python versions** | Bring your own interpreter. | `uv` can download and pin the interpreter (`.python-version`). |
| **Running tools** | Install into your env, or deal with `pipx`. | `uv run <cmd>` / `uvx` runs tools in isolated envs. |

Concretely for this repo:

- `pyproject.toml` is the **source of truth** for dependencies.
- `uv.lock` pins the **exact** versions of everything (including transitive deps) so the
  environment is reproducible on any machine.
- `requirements.txt` is present only as an **export/fallback** for tools that expect it —
  it is not where you edit dependencies.
- `.python-version` pins **Python 3.11** for this project.
- The build backend is `uv_build` (see `[build-system]` in `pyproject.toml`), so `uv` can
  build and install the package itself, which is what makes the `weather-mcp` script work.

Common `uv` commands you'll use here:

```bash
uv sync          # create/update .venv to exactly match uv.lock
uv run <cmd>     # run a command inside the project environment
uv add <pkg>     # add a dependency, updating pyproject.toml + uv.lock
uv lock          # re-resolve uv.lock from pyproject.toml
uv build         # build the package (uses uv_build)
```

If you know `pip`, the mental translation is: **`uv run python …` ≈ `pip` after activating
a venv you made and maintained by hand** — just faster and reproducible.

---

## Project layout

```
13_MCP/
├── pyproject.toml          # project metadata, deps, console scripts, build backend
├── uv.lock                 # exact pinned dependency graph (uv)
├── requirements.txt        # exported fallback for pip-based tooling
├── .python-version         # pins Python 3.11
├── README.md               # this file
└── src/
    └── weather_mcp/
        ├── __init__.py     # package docstring
        └── server.py       # the MCP server: MCPServer, the tool, and main()
```

---

## How to run the server

### Prerequisites

- [`uv`](https://docs.astral.sh/uv/) installed (`uv --version`)
- Python 3.11 (uv will fetch it if needed)
- Internet access (the tool calls `https://wttr.in`)

Set up the environment once — this creates `.venv` and installs exactly what `uv.lock`
pins:

```bash
uv sync
```

### Run it (script entry point)

This is the canonical way to run it, using the `weather-mcp` console script declared in
`pyproject.toml`:

```bash
uv run weather-mcp
```

That maps to `weather_mcp.server:main`, which calls `mcp.run(transport="stdio")`. The
server then waits for a client on **stdin/stdout** — so if you run it in a plain terminal
it will look like it "hangs". That's correct: a stdio server has nothing to print and no
UI. Use the Inspector (next) to actually interact with it.

### Run it in the MCP Inspector

The MCP SDK ships a CLI (`mcp[cli]`) with an Inspector — a web UI to list tools and call
them by hand. This is the best way to see it work:

```bash
uv run mcp dev src/weather_mcp/server.py
```

Open the printed URL, click **Connect**, then:
1. Go to the **Tools** tab — you'll see `weather` with its `city` argument.
2. Call it with `{"city": "Mumbai"}` — you'll get live weather back.

### Run it as a module

Equivalent to the entry point, useful for debugging:

```bash
uv run python -m weather_mcp.server
```

You can also point the `mcp` CLI at it directly:

```bash
uv run mcp run src/weather_mcp/server.py
```

### Connect a client

To use it inside an MCP host (e.g. Claude Desktop), add it to the host's MCP config.
The host spawns the process and speaks stdio to it:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/13_MCP", "run", "weather-mcp"]
    }
  }
}
```

Or let the SDK write the Claude Desktop config for you:

```bash
uv run mcp install src/weather_mcp/server.py
```

Once connected, the model can answer questions like *"What's the weather in Delhi?"* by
calling the `weather` tool.

---

## How to build your own MCP server

This is the entire recipe, using only the code in `src/weather_mcp/server.py`.

**1. Import the SDK and create a server object.** The `MCPServer` object is your handle to
the protocol — everything you expose hangs off it. The name (`"weather"`) is what clients
see as `serverInfo.name`.

```python
import httpx
from mcp.server.mcpserver import MCPServer

# Initialize the MCP server
mcp = MCPServer("weather")
```

**2. Write your actual logic as a normal function.** Keep it independent of MCP so it's
easy to test and reuse:

```python
async def get_weather(city: str) -> str:
    url = f"https://wttr.in/{city.lower()}?format=%C+%t"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 200:
        return f"Current weather in {city}: {response.text}"
    return "Error: Something went wrong"
```

**3. Expose it as a tool with `@mcp.tool()`.** Three things define the contract the model
sees:
- the **function name** (`weather`) → the tool name,
- the **type hints** (`city: str`) → the generated input JSON Schema,
- the **docstring** → the tool description, including the `Args:` block the model reads to
  fill arguments correctly.

```python
@mcp.tool()
async def weather(city: str) -> str:
    """Get weather for a city.

    Args:
        city: Name of the city (e.g. San Francisco, Los Angeles, Mumbai, Delhi)
    """
    return await get_weather(city)
```

Because you gave it a clean type hint and docstring, clients receive a fully-formed tool
definition for free:

```json
{
  "name": "weather",
  "description": "Get weather for a city.\n\n    Args:\n        city: ...",
  "inputSchema": {
    "properties": { "city": { "type": "string" } },
    "required": ["city"],
    "type": "object"
  }
}
```

**4. Add an entry point.** `main()` starts the protocol loop on a transport; the
`if __name__ == "__main__"` block makes the file runnable directly.

```python
def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

**5. Register the entry point in `pyproject.toml`** so it becomes a runnable command:

```toml
[project.scripts]
weather-mcp = "weather_mcp.server:main"
```

**To add more tools**, repeat step 3 — decorate another typed, documented function. To
expose *read-only data* instead of an action, add a resource; to ship reusable prompt
templates, add a prompt (the same `MCPServer` instance offers `.resource()` and
`.prompt()`).

---

## Troubleshooting

- **Terminal looks frozen after `uv run weather-mcp`** — expected. A `stdio` server waits
  silently for a client. Use `uv run mcp dev src/weather_mcp/server.py` to interact with it.
- **`VIRTUAL_ENV ... does not match the project environment path .venv`** — you have an
  unrelated venv activated. Run `deactivate`, or use `uv run --active`. Not fatal; `uv`
  just warns and uses the project `.venv`.
- **Weather says "Error: Something went wrong"** — the upstream `wttr.in` call failed;
  check your internet connection.
- **`uv: command not found`** — install uv, then re-run `uv sync`.

---

Built with the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and
managed with [uv](https://docs.astral.sh/uv/).
