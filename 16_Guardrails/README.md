# Agent Guardrails

Guardrails are safety checks and content filters placed around an AI agent. Just like guardrails on a mountain highway prevent cars from sliding off the edge, guardrails in an AI system prevent the model from leaking private data, executing harmful actions, falling for prompt injections, or saying something unsafe.

They are implemented as **middleware**—interceptors that inspect and modify data flowing in and out of the agent at every stage.

---

## 1. Where Guardrails Intervene (The Lifecycle)

Guardrails do not just check the final text; they sit at three critical choke points:

1. **Before Agent (Input Gate):**
* *Analogy:* The bouncer at the club door.
* Runs the moment the user sends a message, *before* any LLM token is spent or tool is called.
* Used for rate limiting, authentication checks, and blocking blacklisted keywords or malicious prompts immediately.


2. **Around Model & Tool Calls (Action Gate):**
* *Analogy:* Dual-key confirmation for high-stakes actions.
* Runs right before a tool executes or when data is sent to the LLM.
* Used to sanitize sensitive parameters or pause execution for human approval before dangerous tools run.


3. **After Agent (Output Gate):**
* *Analogy:* The final quality assurance inspector before shipping a package.
* Runs after the LLM generates a response, right before the user sees it.
* Used to verify that the generated answer is safe, compliant, and free of hallucinated sensitive data.



---

## 2. Two Implementation Approaches

| Type | How It Works | Strengths | Weaknesses | Best Used For |
| --- | --- | --- | --- | --- |
| **Deterministic Guardrails** | Rule-based code (Regex, keyword blacklists, exact matches). | **Blazing fast, 100% predictable, $0 cost.** | Can miss subtle phrasing, sarcasm, or typos. | Blocking API keys, regex-matching credit cards, banned phrases. |
| **Model-Based Guardrails** | A secondary, lightweight LLM (e.g., `mini` model) acting as a judge. | **Understands context, intent, tone, and nuance.** | Slower (adds latency) and incurs extra token costs. | Detecting toxicity, sentiment analysis, compliance review. |

---

## 3. Core Guardrail Patterns

### A. PII Detection & Sanitization

Protects **Personally Identifiable Information** (emails, credit cards, phone numbers, API keys) from reaching external LLM servers or application logs.

* **Strategies:**
* `redact`: Replaces data with a label (e.g., `[REDACTED_EMAIL]`).
* `mask`: Hides part of the data (e.g., `****-****-****-1234`).
* `hash`: Converts data to an irreversible unique string (`a8f5f167...`).
* `block`: Halts execution immediately and raises an error.



### B. Human-in-the-Loop (HITL)

High-stakes operations (like issuing refunds, dropping database tables, or emailing customers) should not happen automatically.

* The middleware **pauses** execution right before the tool executes.
* It alerts a human reviewer with the exact arguments.
* The human can **Approve**, **Edit** the inputs, or **Reject** the action before the agent resumes.

---

## 4. Defense-in-Depth (Layered Guardrails)

In production, never rely on a single guardrail. Guardrails are stacked in sequential layers:

```text
[ User Prompt ]
       │
       ▼
[ Layer 1: Keyword & Injection Filter ]  ──► (Banned? Jump to end)
       │
       ▼
[ Layer 2: PII Redaction ]              ──► (Strip credit cards/emails)
       │
       ▼
[ Agent Loop / Tool Selection ]
       │
       ▼
[ Layer 3: Human Approval (HITL) ]      ──► (Pause if tool is high-risk)
       │
       ▼
[ Layer 4: Output Safety Evaluator ]    ──► (LLM scans answer for compliance)
       │
       ▼
[ Verified Safe Output to User ]

```


Built-in PII types:
email - Email addresses
credit_card - Credit card numbers (Luhn validated)
ip - IP addresses
mac_address - MAC addresses
url - URLs
Configuration options:
Parameter	Description	Default
pii_type	Type of PII to detect (built-in or custom)	Required
strategy	How to handle detected PII ("block", "redact", "mask", "hash")	"redact"
detector	Custom detector function or regex pattern	None (uses built-in)
apply_to_input	Check user messages before model call	True
apply_to_output	Check AI messages after model call	False
apply_to_tool_results	Check tool result messages after execution	False

---

## 5. What's Actually In This Repo (The Code)

This project is a working playground that turns the ideas above into real code. It has **four small programs**, each in its own folder under `src/`. Each one is a self-contained example you can run on its own.

### Project layout

```text
16_Guardrails/
├── pyproject.toml          # Project config, dependencies, and CLI commands
├── uv.lock                 # Locked dependency versions (managed by `uv`)
├── .python-version         # Python version (3.11)
├── README.md               # This file
└── src/
    ├── 16_guardrails/      # Placeholder main entry point (just prints hello)
    ├── pii_gr/             # Example 1: PII detection & redaction
    ├── hitl/               # Example 2: Human-in-the-Loop approval
    └── custom_gr/          # Example 3: Custom guardrail middleware
```

### Example 1 — PII Guardrail (`src/pii_gr/`)

Shows how to catch **private data** before it reaches the LLM.

* Defines two test tools: a customer-service tool and an email tool.
* Uses `PIIMiddleware` three times, each with a different rule:
  * **Emails** → `redact` (replaced with `[REDACTED_EMAIL]`).
  * **Credit cards** → `mask` (only last 4 digits visible).
  * **API keys** → `hash` (turned into a fingerprint), using a custom regex `sk-[a-zA-Z0-9]{32}`.
* Runs one demo prompt containing an email, a card number, and a secret key, then prints what the LLM *actually* received vs. what you typed.

### Example 2 — Human-in-the-Loop (`src/hitl/`)

Shows how to **pause and ask a human** before a risky action runs.

* Defines three tools: `search`, `send_email`, and `delete_database`.
* Uses `HumanInTheLoopMiddleware` with an `interrupt_on` map:
  * `search` → `False` (runs automatically).
  * `send_email` and `delete_database` → `True` (pauses for approval).
* Runs an interactive session. When a sensitive tool is triggered, it prints the pending tool + arguments and asks `y/n`. On "yes" it resumes with approval, otherwise it resumes with rejection.

### Example 3 — Custom Guardrails (`src/custom_gr/`)

Shows how to **write your own middleware** from scratch by subclassing `AgentMiddleware`.

* `ContentFilterMiddleware` — a *deterministic* input gate that blocks banned keywords (hack, exploit, malware, ddos) before the LLM is called, via the `before_agent` hook.
* `SafetyGuardrailMiddleware` — a *model-based* output gate that sends the finished answer to a second "judge" LLM and asks it to reply only `SAFE` or `UNSAFE`, via the `after_agent` hook.
* `build_guarded_agent()` wires both layers together, and `main()` runs two tests:
  * **Test 1** — a safe query (both gates pass).
  * **Test 2** — a query with a banned keyword (blocked at the input gate, zero tools called).

---

## 6. How to Run It

> **Prerequisite:** You need a `.env` file with your API credentials, because every example reads `CMD_API_KEY` and `CMD_BASE_URL` from the environment.

```bash
# 1. Install dependencies (uses the `uv` package manager)
uv sync

# 2. Run any of the examples
uv run pii-gr        # Example 1: PII detection
uv run hitl          # Example 2: Human-in-the-loop (interactive)
uv run custom-gr     # Example 3: Custom guardrails
```

The `.env` file should look like this (values are examples only):

```text
CMD_API_KEY=your_api_key_here
CMD_BASE_URL=your_base_url_here
```

> **Note:** The model used throughout is `deepseek/deepseek-v4-flash`. If you want to use a different model, change the `model=` line in the file you're running.

---

## 7. Notes (Things Still Missing)

These are loose ends I noticed while reading the code, so nothing gets forgotten:

* **No `.env` file is committed** — the code calls `load_dotenv()` and reads `CMD_API_KEY` / `CMD_BASE_URL`, but there's no `.env` in the repo. You must create it yourself before running.
* **`16_guardrails/__init__.py` is just a placeholder** — `main()` only prints `"Hello from 16-guardrails!"`. It doesn't tie the three examples together yet.
* **The `api_key` PII rule has a misleading comment** — the code comment says it's a "hard stop", but the strategy is actually `hash`, not `block`. (Worth fixing the comment or switching to `block`.)
* **`pyproject.toml` still has a placeholder description** — `description = "Add your description here"` could be updated to something meaningful.
* **No automated tests** — each module has a manual `main()` demo, but there are no `pytest`/test files.
* **No `.env.example`** — adding one would make setup much clearer for new users (see the example above).
* **No `__init__.py` docs or docstrings** — the modules are self-documenting via comments, but a short module-level docstring would help.
