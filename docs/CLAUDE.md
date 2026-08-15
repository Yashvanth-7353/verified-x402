# CLAUDE.md — Development Guidance for AI Coding Agents Working on Verified

## 1. Purpose

This document orients an AI coding agent (or any future contributor) working on the Verified codebase. It summarizes the architecture, states the invariants that must never be violated, and lists rules to follow when implementing or modifying any part of the system. Read this alongside PRD.md, ARCHITECTURE.md, DATA_MODEL.md, DESIGN.md, AGENTS.md, TASKS.md, TESTING.md, and THREAT_MODEL.md — this file does not restate their full content, only the operational essentials.

## 2. What Verified Is (One Paragraph)

Verified is a local-first verification layer, running on a Jetson Nano, that validates AI-agent structured output (JSON/SQL/function-call args) against a schema and safety policy, deterministically repairs what it safely can, and — only when necessary — escalates unresolved issues to a paid semantic-repair API gated by an x402 payment settled on Algorand via the GoPlausible AVM facilitator. Every request produces a cryptographically bound verification receipt; receipts are periodically batched into a Merkle tree and anchored on Algorand for tamper-evident auditability. Core rule: **no valid proof, no execution.**

## 3. Invariants That Must Never Be Violated

These are hard rules, not preferences. Any change that would break one of these should be stopped and flagged, not silently worked around:

1. **Fail closed, always.** Any uncertainty, failure, or unresolved issue must result in `rejected`, never in a default/fallback `verified`. (Architecture Principle 8, ARCHITECTURE.md §10)
2. **Verify after repair, unconditionally.** No output — deterministic-repaired or semantic-repaired — may be marked `verified`/`verified_repaired` without passing through the full local validation pipeline again after repair. Re-validation is not optional and is not a different code path from initial validation. (Architecture Principle 4, DESIGN.md §6)
3. **No semantic repair without settled payment.** The semantic-repair API must never be called with a real payload unless the corresponding x402 payment has reached `payment_status = settled` via the GoPlausible AVM facilitator. (Architecture Principle 3, DATA_MODEL.md §4)
4. **Privacy filtering runs first and unconditionally.** No payload content may be sent to the semantic-repair API, logged, or otherwise leave the local trust boundary before the Privacy Filter stage has run on it. (ARCHITECTURE.md §4.4, DESIGN.md §10)
5. **Raw payloads never touch Algorand.** Only Merkle roots (and necessary transaction metadata) are anchored on-chain. Never place raw payload content, unhashed receipt content, or individually identifying verification detail on-chain. (Architecture Principle 6, PRD.md FR10)
6. **Unsafe SQL is never silently auto-rewritten.** Deterministic repair must never "fix" a SQL-safety finding by rewriting query semantics. Unsafe SQL is rejected or (only if a future policy explicitly and narrowly allows it) escalated for classification — never silently patched. (ARCHITECTURE.md §4.2, THREAT_MODEL.md T3)
7. **Every request produces exactly one receipt, regardless of outcome.** There is no code path that completes processing of a request without producing a `VerificationReceipt`, including rejections. (Architecture Principle 5, DESIGN.md §9)
8. **Deterministic repair must be a pure function.** No network calls, no randomness, no model inference inside deterministic repair. If a fix requires judgment beyond the enumerated rule set, it belongs in the semantic-repair path or is not repairable — it does not belong in deterministic repair "just this once." (ARCHITECTURE.md §4.2, DESIGN.md §5)
9. **Anchoring failures never block receipt issuance, and vice versa.** These are separate concerns: the receipt gates execution; anchoring provides longer-horizon audit proof. A pending/failed anchor must not invalidate an already-issued receipt, and receipt issuance must never wait on anchoring to complete. (ARCHITECTURE.md §10)

## 4. Security & Privacy Rules

- Treat the Jetson's local record store as containing sensitive raw payload data; never add code paths that copy raw payload content into logs, receipts, external API calls (beyond the explicitly filtered semantic-repair forwarding), or any Algorand-bound artifact.
- Treat the semantic-repair API's response as **untrusted input**, always. Never add a code path that accepts its output without re-running it through the full validation pipeline.
- Treat the GoPlausible AVM facilitator and Algorand network as trusted only for what they are scoped for (payment verification/settlement and root anchoring) — do not extend trust to them for payload confidentiality or validation-logic correctness.
- When implementing the privacy filter, default to being conservative (over-filter rather than under-filter) given that the taxonomy is a hackathon-scope TBD per THREAT_MODEL.md T8 — false positives (over-redaction) are a UX cost; false negatives are a privacy incident.
- Do not implement request-level replay/idempotency handling in a way that silently reuses a receipt across genuinely different output payloads — always re-derive from `output_hash`, never just `request_id`, when deciding whether a cached receipt is safe to reuse (see DESIGN.md §7, THREAT_MODEL.md T6 — this is a flagged, unresolved area; be conservative until the team explicitly decides the policy).

## 5. API/Interface Boundaries

- The **validation pipeline contract** (schema → type → syntax → SQL safety, with privacy filtering running first) is the single source of truth for what counts as valid. Do not duplicate validation logic elsewhere (e.g., do not add ad hoc checks inside the escalation decision logic or the receipt generator — those components consume `ValidationFinding` output, they do not produce their own).
- The **Escalation Decision Logic** is the only component that decides deterministic-repair vs. semantic-repair vs. reject, based on `ValidationFinding.repairable` classification. Do not scatter this decision across multiple components.
- The **Receipt Generator** only ever consumes a completed `VerificationResult` — it does not itself run validation, call the semantic-repair API, or talk to the facilitator.
- x402/payment logic and semantic-repair-API logic are separate components (`x402 Payment Handler` vs. `Semantic-Repair API Client`) even though they're sequenced together in the escalation flow — keep them independently testable and independently mockable (see TESTING.md §6, §7).
- See ARCHITECTURE.md §3 for the full component table and DESIGN.md §4–§5 for the exact stage/repair contracts before adding or modifying a component.

## 6. x402 / Algorand Requirements

- All payment flows must go through the GoPlausible AVM facilitator for verification and settlement on Algorand — do not introduce an alternate payment path or a different facilitator without updating ARCHITECTURE.md and DATA_MODEL.md accordingly, since `PaymentMetadata.facilitator` and `.settlement_network` are currently modeled as fixed constants (DATA_MODEL.md §3.5).
- The HTTP 402 challenge/response shape must remain a distinct response state from a completed verification receipt (DESIGN.md §3.2) — do not collapse these into a single ambiguous response type.
- Do not hardcode payment pricing, asset choice, or expiry conventions without first resolving the corresponding TBD in ARCHITECTURE.md §5.1/§11 and recording the decision (update the doc when you do — see §8 below).
- Anchoring logic must only ever submit a Merkle root (plus necessary transaction metadata) to Algorand — if you find yourself adding a field to the anchoring transaction that isn't the root itself or standard transaction metadata, stop and reconsider against Invariant 5 above.

## 7. Development Priorities (Hackathon Context)

Follow TASKS.md's milestone ordering. In priority order for a coding agent picking up unassigned work:
1. Resolve any outstanding Milestone 0 (Foundational Decisions) items relevant to the task at hand before writing pipeline code that depends on them — do not silently invent a schema formalism, hash algorithm, or SQL dialect choice; if it's undecided, flag it rather than guessing permanently into the codebase.
2. Local validation pipeline and deterministic repair (Milestones 1–2) before payment/escalation code (Milestones 3–4) — the local path must work standalone first.
3. Receipts and the local record store (Milestones 5–6) before Merkle anchoring (Milestone 7) — anchoring depends on records existing.
4. The execution-gating demo consumer (Milestone 8) and full demo rehearsal (Milestone 9) are the last-mile priorities once the above are functioning end-to-end.

## 8. Rules That Must Not Be Violated (Process)

- **Do not invent technology choices not already specified.** If a TBD is encountered (see the consolidated TBD tables in ARCHITECTURE.md §11, DATA_MODEL.md §5, DESIGN.md §12), either surface it for a decision or implement behind a clearly marked placeholder — do not quietly pick something and leave it undocumented.
- **When a TBD is resolved during implementation, update the relevant doc(s).** These nine documents are meant to stay accurate to the running system, not to freeze as historical planning artifacts.
- **Do not weaken fail-closed behavior for convenience during debugging/demo prep.** It is tempting, under time pressure, to add a bypass ("just trust it for the demo") — this directly undermines the project's core value proposition and must not be done, even temporarily, in code that could accidentally ship into the demo path.
- **Do not add features that place raw payload data on-chain**, even for debugging visibility — use local logs (with appropriate privacy-filter awareness) instead, and only put hashes/roots on Algorand.
- **Keep no-code-in-planning-docs discipline**: PRD.md, ARCHITECTURE.md, DATA_MODEL.md, DESIGN.md, AGENTS.md, THREAT_MODEL.md are architecture/requirements documents, not implementation references — do not turn them into pseudo-code dumps as the project evolves; keep implementation detail in the codebase itself.

## 9. Where to Look for What

| Question | Document |
|---|---|
| What is Verified for, and what's in/out of MVP scope? | PRD.md |
| How do the components fit together, what are the trust boundaries? | ARCHITECTURE.md |
| What does a request/receipt/record actually contain? | DATA_MODEL.md |
| What are the API-level contracts and error-handling rules? | DESIGN.md |
| How does an agent integrate with this system? | AGENTS.md |
| What needs to be built, in what order? | TASKS.md |
| How should a given piece of behavior be tested? | TESTING.md |
| What could go wrong, and how is it mitigated? | THREAT_MODEL.md |
| What must a coding agent never do while working on this? | This document |
