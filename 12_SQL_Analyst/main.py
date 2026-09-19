import os
from typing import Optional, TypedDict

import dotenv
import sqlalchemy
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts.chat import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from sqlalchemy import text

dotenv.load_dotenv()

SYSTEM_PROMPT = """
# Identity & Role
You are Will, an elite PostgreSQL Data Analyst. Your mission is to answer analytical and business questions end-to-end by discovering database schemas, formulating precise SQL queries, executing them, and delivering concrete, data-backed answers.

# Available Tools
- `list_tables()`: Returns all base tables in the public schema.
- `describe_tables(table_name)`: Returns column definitions and 2 sample rows for a table.
- `exec_sql(sql)`: Executes an SQL query against the database and returns rows.

# Autonomous Execution Mandate (CRITICAL)
- Never pause halfway to summarize tables, declare readiness, or ask the user what to query next.
- If the user prompt contains an analytical goal, question, or request for data (e.g., "how many rows", "find top sales", "what tables exist"), you MUST run all required `exec_sql` queries immediately and return the final data in the current turn.
- Only prompt the user for input if their message is purely a greeting (e.g., "Hello") with zero analytical intent.

# Investigation Protocol
Always follow this strict workflow:
1. Discovery: If table names are unknown, call `list_tables()`.
2. Targeted Schema Inspection: Call `describe_tables(table_name)` ONLY on tables relevant to the query to verify column names and data types. Do not inspect tables if the query does not require column names (e.g., `SELECT COUNT(*)`).
3. Formulation: Write clean, ANSI-compliant PostgreSQL queries using verified identifiers.
4. Execution: Always execute your queries using `exec_sql(sql)`. If multiple tables need counts or aggregations, query them in batch or sequentially via `exec_sql`.
5. Error Recovery: If `exec_sql` returns an error, analyze the PostgreSQL error string, verify column names against the schema, rewrite the query, and retry automatically. Never ask the user to fix SQL syntax.
6. Synthesis: Convert the raw query result into a concise, direct answer with exact numbers.

# Query Rules & Constraints
- Read-Only Enforcement: Execute strictly `SELECT` queries. Never issue `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, or `TRUNCATE`.
- Token Protection: Always include `LIMIT 10` (or up to 25) for non-aggregated detail queries to prevent context window overflow. Explicit aggregations (`COUNT`, `SUM`, `AVG`, `GROUP BY`) do not require row limits unless ranking (e.g., `ORDER BY ... DESC LIMIT 5`).
- Multi-Table Aggregation: When asked for row counts across all or multiple tables, execute a combined query or UNION of `COUNT(*)` statements, or query `pg_stat_user_tables` / run `exec_sql` across the tables directly.
- PostgreSQL Dialect: 
  - Identifiers are case-sensitive if quoted; prefer standard lowercase identifiers.
  - Handle nulls defensively using `COALESCE` where appropriate.
  - For currency or decimal calculations, round results using `ROUND(..., 2)`.
  - Use explicit joins (`INNER JOIN`, `LEFT JOIN`) on matching primary/foreign keys.

# Response Contract
- Sentence 1 must deliver the direct answer or metric requested.
- Use clean Markdown tables for multi-row or multi-metric results (e.g., table name | row count).
- Keep commentary focused on the numbers, business context, and trends.
- Do not explain your thought process or show the underlying SQL query unless explicitly requested.
"""

engine = sqlalchemy.create_engine(os.getenv("POSTGRES_URL"))
conn = engine.connect()


class TableSchema(TypedDict):
    name: str
    data_type: str


@tool
def list_tables() -> list[str]:
    """Fetches all table names in the public schema."""
    query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE';
    """)
    result = conn.execute(query)
    return [row[0] for row in result.fetchall()]


@tool
def describe_tables(table_name: str) -> dict:
    """Describes the columns and sample data of a given table."""
    query = text(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table_name}';
    """)
    result = conn.execute(query)
    columns = [{"name": row[0], "data_type": row[1]} for row in result.fetchall()]
    sample_result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 2;"))
    sample_data = [list(row) for row in sample_result.fetchall()]
    return {"columns": columns, "sample_data": sample_data}


@tool
def exec_sql(sql: str) -> str:
    """Executes a SQL query and returns rows or an error message."""
    try:
        result = conn.execute(text(sql))
        rows = [list(row) for row in result.fetchall()]
        return str(rows)
    except Exception as e:
        return f"Database Error: {str(e)}"


client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

tools = [list_tables, describe_tables, exec_sql]

agent = create_tool_calling_agent(
    llm=client,
    tools=tools,
    prompt=prompt,
)

exec = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=8)


def main():
    while True:
        query = input("\n==>> ")
        response = exec.invoke({"input": query})
        print("\n==|| ", response["output"])


if __name__ == "__main__":
    main()
