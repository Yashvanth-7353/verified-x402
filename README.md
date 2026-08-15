# Verified

**A local-first verification layer for AI agent output — no valid proof, no execution.**

Verified sits between an AI agent's structured output (JSON, SQL, function-call arguments) and whatever system would execute it. It runs on a Jetson Nano, validates and repairs output locally and deterministically wherever possible, and only pays for AI-assisted semantic repair when it's genuinely needed — metered via **x402** and settled on **Algorand** through the **GoPlausible AVM facilitator**. Every request produces a cryptographically bound verification receipt, and receipts are periodically anchored on Algorand for tamper-evident auditability.

Built for the **Algorand Global x402 Challenge**.

---

## Why

AI agents increasingly take real actions — running SQL, calling APIs, submitting transactions — based on LLM-generated structured output. That output is often malformed, mistyped, or unsafe, and most systems either trust it blindly or bolt on ad hoc, per-integration checks. There's no standard way for an execution system to demand *proof* that an output was verified before acting on it, and no cheap way to get semantic-level repair without sending every payload to a paid model regardless of need.

Verified fixes what it can locally, for free. It only pays for help when local checks can't resolve the issue — and even then, it never trusts the fix without re-checking it.

## Core Principle

> **No valid proof, no execution.**

A downstream system should never execute an AI agent's output without a verification receipt confirming it was checked — structurally valid, type-correct, syntactically sound, safe, and (if repaired) re-validated after repair.

## How It Works

1. **Local validation** — schema validation, type checking, syntax checking, SQL safety checks, and privacy filtering all run on-device, with no network call.
2. **Deterministic repair** — a bounded, rule-based set of safe fixes is applied where the correct fix is unambiguous. No model inference, no guessing.
3. **Escalation (only when necessary)** — if an issue can't be safely resolved locally, Verified returns an HTTP `402 Payment Required`. The agent's client responds with a signed `X-PAYMENT` per the x402 protocol. The **GoPlausible AVM facilitator** verifies and settles the payment on **Algorand**.
4. **Semantic repair** — only after payment is settled, the (privacy-filtered) payload is sent to a paid semantic-repair API.
5. **Re-validation** — the repaired output is never trusted directly. It's re-run through the exact same local validation pipeline before it can pass.
6. **Verification receipt** — every request, regardless of outcome, produces a receipt: cryptographically bound to the output, schema, repair details, and validator version.
7. **Audit anchoring** — verification records are periodically batched into a Merkle tree, and the root is anchored on Algorand. Raw payloads never leave the device and never touch the chain — only the Merkle root does.

```
Agent Output → Privacy Filter → Local Validation → Deterministic Repair
                                                          │
                                          resolved ───────┼─────── unresolved
                                              │                        │
                                       Re-validate              x402 402 Challenge
                                              │                        │
                                          Receipt          X-PAYMENT → GoPlausible → Algorand
                                              │                        │
                                              │                 Semantic Repair API
                                              │                        │
                                              │                 Re-validate (never skipped)
                                              │                        │
                                              └────────────── Receipt (verified / verified-repaired / rejected)
                                                                        │
                                                          Local Record → Merkle Batch → Algorand Anchor
```

## Architecture Principles

| # | Principle |
|---|---|
| 1 | Local-first — verify deterministically on-device whenever possible |
| 2 | Privacy-first — confidential payloads never leave the device unless escalation is truly needed |
| 3 | Pay only when needed — x402 triggers only for genuine semantic-repair escalation |
| 4 | Verify after repair — a repaired output is never trusted without re-validation |
| 5 | Proof before execution — downstream execution requires a valid receipt |
| 6 | Off-chain data, on-chain evidence — raw payloads never touch Algorand |
| 7 | Tamper evidence — verification evidence is cryptographically bound to output, schema, policy, repair, and validator version |
| 8 | Fail closed — uncertainty or invalid proof blocks execution, never defaults to a pass |
| 9 | Hackathon feasibility — a demonstrable end-to-end MVP over unnecessary complexity |

## Stack

- **Edge runtime:** Jetson Nano
- **Payments:** x402 (HTTP 402 → signed `X-PAYMENT`)
- **Payment facilitator:** GoPlausible AVM Facilitator
- **Settlement / audit anchoring:** Algorand

Specific schema formalism, hash algorithm(s), SQL dialect coverage, and a handful of other implementation choices are tracked as open decisions rather than assumed — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §11 and [`docs/TASKS.md`](docs/TASKS.md) Milestone 0.

## Documentation

Full architecture and planning docs live in [`/docs`](docs):

| Doc | Covers |
|---|---|
| [PRD.md](docs/PRD.md) | Product vision, goals, scope, user flows, demo scenario |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System components, trust boundaries, data/control flow (Mermaid diagrams) |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | Conceptual data model — requests, receipts, hashes, payment/audit records |
| [DESIGN.md](docs/DESIGN.md) | API/interface design, error handling, idempotency, execution-gating model |
| [AGENTS.md](docs/AGENTS.md) | How AI agents integrate — local flow, escalation, payment, receipt handling |
| [TASKS.md](docs/TASKS.md) | Dependency-ordered implementation roadmap and milestones |
| [TESTING.md](docs/TESTING.md) | Test strategy and scenarios across every pipeline stage |
| [THREAT_MODEL.md](docs/THREAT_MODEL.md) | Threats, mitigations, and residual risk |
| [CLAUDE.md](docs/CLAUDE.md) | Invariants and rules for AI coding agents contributing to this repo |

## Status

Hackathon MVP in development for the **Algorand Global x402 Challenge**. Architecture and planning are complete; see [TASKS.md](docs/TASKS.md) for current build progress and open decisions.

## Demo Scenario

1. An agent submits output that's schema-valid but contains unsafe SQL — Verified catches it locally and rejects it. No auto-rewrite, no silent pass.
2. A second output needs a genuinely ambiguous field repair — Verified issues a 402, the client pays via x402, GoPlausible settles on Algorand, the semantic-repair API returns a fix, and Verified re-validates it before issuing a `verified-repaired` receipt.
3. The verification record is anchored on Algorand as part of a Merkle batch — provably included, with the raw payload never touching the chain.

## License

TBD.
