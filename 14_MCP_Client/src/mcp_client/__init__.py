import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()  # load environment variables from .env


def _resolve_server_command(server_script_path: str) -> str:
    """Pick the interpreter used to launch the MCP server.

    Precedence: MCP_SERVER_COMMAND env var -> the server project's own
    .venv interpreter -> the current interpreter.
    """
    env_command = os.getenv("MCP_SERVER_COMMAND")
    if env_command:
        return env_command

    venv_python = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    script_path = Path(server_script_path).resolve()
    for parent in script_path.parents:
        candidate = parent / ".venv" / venv_python
        if candidate.exists():
            return str(candidate)

    return sys.executable

# **`contextlib`** is Python’s built-in toolkit for managing resource cleanup (closing files, network sockets, or database connections) using `with` and `async with`.

# **`AsyncExitStack`** is a dynamic resource manager. While normal `async with` forces you to hardcode connections upfront, `AsyncExitStack` lets you open an unpredictable number of async resources at runtime (like connecting to multiple MCP servers dynamically). It logs each resource on an internal clipboard and guarantees that every single connection cleanly closes in reverse order (LIFO), even if your program crashes halfway through.

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = AsyncOpenAI(
            api_key=os.getenv("CMD_API_KEY"),
            base_url=os.getenv("CMD_BASE_URL"),
        )
        self.model = "deepseek/deepseek-v4-flash"

    async def connect_to_server(self, server_script_path: str, command: Optional[str] = None):
        """Connect to an MCP server
        Args:
            server_script_path: Path to the server script (.py or .js)
            command: Interpreter to launch the server with. Defaults to the
                server project's own .venv python, falling back to the
                current interpreter.
        """
        server_params = StdioServerParameters(
            command=command or _resolve_server_command(server_script_path),
            args=[server_script_path],
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        print("\n\n---------->> CONNECTED TO MCP SERVER <<-------------\n\n")
        tools = response.tools
        print("\n>>> Tools:\n", [tool.name for tool in tools])
    
    async def process_query(self, query: str):
        """Process a query using the LLM and available tools"""
        messages = [
            {"role": "user", "content": query}
        ]

        response = await self.session.list_tools()
        available_tools = [{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            } for tool in response.tools]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=available_tools
        )

        final_text = []

        while True:
            message = response.choices[0].message

            if message.content:
                final_text.append(message.content)

            if not message.tool_calls:
                break

            messages.append(message.model_dump(exclude_none=True))

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments or "{}")

                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                result_text = "\n".join(
                    block.text
                    for block in result.content
                    if getattr(block, "type", None) == "text"
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text,
                })

            # Get next response from the LLM
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=available_tools
            )

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
    
        while True:
            try:
                query = (await asyncio.to_thread(input, "\nQuery: ")).strip()
    
                if query.lower() == 'quit':
                    break
    
                response = await self.process_query(query)
                print("\n" + response)
    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

# Main entry point to the MCP client
async def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(prog="mcp-client", description="MCP client")
    parser.add_argument("server_script", help="Path to the MCP server script (.py or .js)")
    parser.add_argument(
        "-c", "--command",
        help="Interpreter used to launch the server "
             "(defaults to the server project's .venv python)",
    )
    args = parser.parse_args(argv)

    client = MCPClient()
    try:
        await client.connect_to_server(args.server_script, args.command)
        await client.chat_loop()
    finally:
        await client.cleanup()


def cli() -> None:
    """Synchronous console-script entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
