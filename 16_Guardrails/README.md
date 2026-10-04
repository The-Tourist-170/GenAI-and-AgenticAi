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
