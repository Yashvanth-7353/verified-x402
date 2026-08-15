# AGENTS.md — Verified

## 1. Purpose

This document defines how AI agents interact with Verified: the local validation flow, escalation to semantic repair, the x402 payment flow from the agent's perspective, receipt handling, and the "no valid proof, no execution" model as it applies to agent behavior. It complements ARCHITECTURE.md (system-internal view) and DESIGN.md (API/interface view) with an agent-centric perspective.

## 2. What an Agent Is, In This System

An "agent" here is any AI-driven process that produces structured output (JSON, SQL, function-call arguments) intended to be acted on by some downstream system. Verified does not assume anything about the agent's internal architecture (single LLM call, multi-step planner, tool-using agent framework, etc.) — the only contract is the shape of the output submitted for verification (DATA_MODEL.md §3.1).

## 3. Agent Responsibilities

An agent (or its orchestrating client) integrating with Verified is responsible for:

1. **Submitting a well-formed verification request** — output payload, output type, and a reference to the applicable schema/policy (DATA_MODEL.md §3.1).
2. **Holding (or delegating) payment capability** — if escalation to semantic repair is required, the agent's client must be able to respond to an HTTP 402 challenge with a signed `X-PAYMENT` per x402. Whether the agent itself holds signing keys or delegates to a separate wallet-holding client component is an integration choice (PRD.md §4, Non-Goals) — Verified does not mandate a specific custody model.
3. **Not bypassing rejection** — an agent (or the system around it) must not proceed to execute a rejected output. This is a behavioral/integration requirement on the agent's side, enforced structurally on the downstream execution system's side (§6).
4. **Not fabricating or reusing receipts** — an agent must not attempt to present a receipt for a different output than the one actually executed; this is checked via `output_hash` matching (DESIGN.md §11).

## 4. Agent-Facing Flow

### 4.1 Local-only verification (no payment)

1. Agent produces structured output.
2. Agent submits a verification request to Verified, referencing the applicable schema.
3. Verified runs local validation (and deterministic repair, if applicable) and returns a `VerificationReceipt` directly — no payment involved.
4. Agent (or the downstream system it hands the output to) uses the receipt to proceed with execution, per the execution-gating model (§6).

### 4.2 Escalated verification (semantic repair, paid)

1. Agent submits a verification request.
2. Verified determines local resolution isn't possible and responds with an HTTP 402 challenge instead of a receipt.
3. Agent's client constructs and sends a signed `X-PAYMENT` per the x402 protocol, resubmitting to Verified.
4. Verified coordinates with the GoPlausible AVM facilitator to verify and settle the payment on Algorand.
5. On successful settlement, Verified forwards the privacy-filtered payload to the semantic-repair API, receives a candidate fix, re-validates it, and returns a final `VerificationReceipt` (`verified_repaired` or `rejected`, depending on re-validation outcome).
6. If payment verification/settlement fails, Verified returns a `rejected` receipt — the agent does not get a "free" semantic repair attempt, and does not get a silently degraded pass.

### 4.3 Rejection

If a request is rejected (at any stage — initial validation, ineligible for repair, failed payment, or failed re-validation), the agent receives a `rejected` `VerificationReceipt` with `rejection_reasons` (DATA_MODEL.md §3.6). The agent may:
- Modify its output and resubmit as a new request, or
- Accept the rejection and not proceed to execution.

An agent must not treat a `rejected` receipt as a basis for execution under any circumstance — there is no "soft pass" state in the model (DESIGN.md §11).

## 5. Receipt Handling by Agents

- Agents should treat a `VerificationReceipt` as an opaque, verifiable artifact — they pass it to the downstream execution system rather than interpreting its internal fields themselves (beyond, optionally, checking `outcome` for their own control flow).
- Agents should not modify, strip, or reconstruct receipt fields; the `receipt_hash` (DATA_MODEL.md §3.7) exists precisely so that any tampering is detectable by the downstream execution system or auditor.
- If an agent needs to prove, after the fact, that a particular output was verified, it should retain the `receipt_id` and, once available, the corresponding Merkle inclusion proof (DATA_MODEL.md §3.9) rather than re-deriving trust from the raw payload alone.

## 6. The "No Valid Proof, No Execution" Model, From the Agent's Side

The core invariant is enforced at the **downstream execution boundary**, not inside the agent itself (Verified cannot force an agent's own code to check a receipt). The design assumes:

- The downstream execution system (whatever actually runs the SQL, calls the API, submits the transaction) is the component that structurally requires a valid `VerificationReceipt` (`outcome ∈ {verified, verified_repaired}`, matching `output_hash`) before acting (DESIGN.md §11).
- Agents integrating with Verified are expected to route their output through this gate as a matter of integration design, not as an optional courtesy — but Verified's guarantee is about the *proof*, not about coercing agent behavior it cannot observe. This is a scope boundary worth being explicit about: Verified verifies and attests; it is the responsibility of the surrounding system (and its operator) to actually wire execution behind the gate.

## 7. What Agents Never See or Control

- Agents do not see or influence the internal deterministic repair rule set beyond the fact that a repair occurred (`RepairInfo`, DATA_MODEL.md §3.4) — they cannot request "please repair it this way."
- Agents do not control whether an issue is classified as deterministically repairable, semantically repairable, or not repairable — that classification is a property of the `ValidationFinding` (DATA_MODEL.md §3.3), determined by the schema/policy and validation pipeline, not by agent request.
- Agents cannot skip privacy filtering — it runs unconditionally before any escalation decision (ARCHITECTURE.md §4.4, DESIGN.md §10).
- Agents cannot see unfiltered internals of what was sent to the semantic-repair API beyond what they themselves submitted — Verified does not expose the filtering logic's decisions as a queryable agent-facing feature in the MVP (future scope, TBD).

## 8. Multi-Agent / Multi-Tenant Considerations (Future Scope Pointer)

The MVP model assumes a single agent (or a small, cooperating set) interacting with a single Verified instance on one Jetson Nano, consistent with PRD.md's MVP scope. Multi-tenant isolation (separate policy sets, separate payment accounting, separate audit trails per agent/tenant) is explicitly future scope (PRD.md §11) and not designed here.
