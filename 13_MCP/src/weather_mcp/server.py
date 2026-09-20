import httpx
from mcp.server.mcpserver import MCPServer

# Initialize the MCP server
mcp = MCPServer("weather")


async def get_weather(city: str) -> str:
    url = f"https://wttr.in/{city.lower()}?format=%C+%t"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 200:
        return f"Current weather in {city}: {response.text}"
    return "Error: Something went wrong"


@mcp.tool()
async def weather(city: str) -> str:
    """Get weather for a city.

    Args:
        city: Name of the city (e.g. San Francisco, Los Angeles, Mumbai, Delhi)
    """
    return await get_weather(city)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
