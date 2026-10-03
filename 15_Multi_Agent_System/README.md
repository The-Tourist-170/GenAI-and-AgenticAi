# Multi Agents System

## Subagents (The Manager & Specialist Team)
In a subagent architecture, a primary "Supervisor" or "Orchestrator" agent treats other autonomous agents as callable tools.
Plaintext
User ◄──► [ Orchestrator ]
                │  ▲
    (Calls Tool)│  │ (Returns Data)
                ▼  │
         [ SQL Subagent ]
How it works: The user only ever talks to the Orchestrator. When the user asks a complex question involving data, the Orchestrator invokes run_sql_analyst(task="..."). The subagent spins up its own internal loop, queries tables, fixes its errors, and returns a concise string back to the Orchestrator.
Why use it: Scratchpad isolation. If your SQL agent runs 5 failed queries and checks 3 schemas, those internal execution tokens remain trapped inside the subagent. The Orchestrator's conversation history with the user stays clean and unpolluted.
When to build it: When a single user prompt requires coordinating across multiple domains (e.g., "Find our top 3 customers from Postgres, search the web for their company headquarters, and draft an outreach email").

Overview

The supervisor pattern is a multi-agent architecture where a central supervisor agent coordinates specialized worker agents. This approach excels when tasks require different types of expertise. Rather than building one agent that manages tool selection across domains, you create focused specialists coordinated by a supervisor who understands the overall workflow.
