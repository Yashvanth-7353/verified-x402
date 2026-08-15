# THREAT_MODEL.md — Verified

## 1. Purpose

This document performs a security and privacy threat model for Verified, covering malicious AI outputs, prompt-injection-derived outputs, unsafe SQL, forged receipts, tampered hashes, replayed payments, payment failures, malicious clients, compromised local components, data leakage, and Algorand/audit integrity. For each threat: description, mitigation (as designed in ARCHITECTURE.md/DESIGN.md/DATA_MODEL.md), and residual risk.

## 2. Scope & Assumptions

- Threat model covers the Verified system as described in ARCHITECTURE.md, operating on a Jetson Nano, interacting with an external semantic-repair API, the GoPlausible AVM facilitator, and the Algorand network.
- Assumes the hackathon MVP scope (PRD.md §10) — some mitigations below are noted as MVP-adequate but not production-hardened.
- Does not cover physical security of the Jetson device itself beyond noting it as a residual risk where relevant (e.g., physical tampering is out of scope for detailed mitigation design here).

## 3. Threats

### T1 — Malicious or adversarial AI-generated output

**Description:** An agent (compromised, misconfigured, or itself manipulated) produces structured output intended to cause harmful downstream action (e.g., destructive SQL, over-privileged function-call arguments) that superficially resembles valid output.

**Mitigation:** Multi-stage validation (schema, type, syntax, SQL safety) is applied unconditionally to every request (ARCHITECTURE.md §4.1). SQL safety checking specifically targets unsafe statement classes (§4.3). Fail-closed design (Architecture Principle 8) means any unresolved blocking finding results in rejection, not a default pass.

**Residual risk:** The SQL safety rule set and privacy/type policies are only as good as what is enumerated in Milestone 0 (TASKS.md) — a sufficiently novel unsafe pattern outside the chosen rule set could pass undetected. This is an inherent limitation of rule/pattern-based safety checking versus exhaustive semantic understanding, and is explicitly why Verified does not claim to guarantee real-world semantic correctness (PRD.md §4, Non-Goals).

### T2 — Prompt-injection-derived output

**Description:** An upstream prompt injection causes the agent to produce structured output that is schema-valid and syntactically correct, but semantically compromised (e.g., a function call with parameters an attacker wants executed, disguised as legitimate).

**Mitigation:** Verified's structural checks (schema/type/syntax/SQL-safety) will catch injected output that violates structural or safety-class constraints. Verified's privacy filter also limits what such output could exfiltrate through the escalation path even if the injected content includes an attempt to smuggle data out via the semantic-repair call (ARCHITECTURE.md §4.4, DESIGN.md §10).

**Residual risk:** Verified is explicitly **not** a semantic-correctness or intent-verification system (PRD.md §4). A structurally valid, policy-compliant, but semantically malicious output (e.g., a legitimate-looking but attacker-intended function call within allowed parameter bounds) is not something structural validation alone can catch. This is a fundamental scope boundary, not a gap to "fix" within Verified's stated purpose — it should be communicated clearly to any operator relying on Verified as their only safeguard.

### T3 — Unsafe SQL

**Description:** An agent produces a SQL statement that is syntactically valid but destructive, overly broad, or otherwise unsafe to execute (e.g., statement classes that could affect more data than intended).

**Mitigation:** Dedicated SQL Safety Checker stage (ARCHITECTURE.md §4.3) runs on all `sql`-typed outputs. Critically, unsafe SQL findings are architecturally barred from deterministic auto-repair (§4.2) — Verified does not attempt to "fix" unsafe SQL into safe SQL by rewriting it, since that rewrite could silently and incorrectly change the query's intended semantics. Unsafe SQL is rejected outright, or (only if explicitly modeled that way in a future policy) escalated for classification assistance — never silently rewritten.

**Residual risk:** As with T1, coverage is bounded by the chosen rule set/dialect (Milestone 0, TBD in ARCHITECTURE.md §4.3). A hackathon-scope rule set will not have production-grade SQL static-analysis depth.

### T4 — Forged verification receipts

**Description:** A malicious actor (agent, compromised client, or man-in-the-middle) attempts to present a fabricated `VerificationReceipt` to a downstream execution system to bypass verification entirely.

**Mitigation:** Receipts are cryptographically hashed over their bound content (`output_hash`, `schema_ref_and_version`, `repair_summary_hash`, `validator_version` — DATA_MODEL.md §3.7). A downstream execution system recomputing/checking `receipt_hash` against the claimed fields can detect a fabricated receipt whose fields don't hash-match. Optional receipt signing (DESIGN.md §12, TBD) would further strengthen this by binding the receipt to Verified's own key, preventing forgery even of internally-consistent-looking fake receipts.

**Residual risk:** In the MVP, if receipt signing (vs. hashing alone) is deferred to future scope (per DESIGN.md §12 TBD), a sophisticated attacker who can compute hashes correctly could construct an internally-consistent fake receipt for output that was never actually verified, since hashing alone proves internal consistency, not *origin* from Verified. **This is flagged as a priority TBD to resolve before treating Verified's receipts as trustworthy in anything beyond a hackathon demo context** — signing (or equivalent, e.g., anchoring individual receipts rather than only batches) closes this gap.

### T5 — Tampered hashes / tampered local records

**Description:** An actor with access to the Jetson's local record store modifies a stored `LocalVerificationRecord` or its receipt after the fact (e.g., changing a `rejected` outcome to `verified` retroactively).

**Mitigation:** Once a record's receipt has been included in an anchored Merkle root (ARCHITECTURE.md §8), any retroactive modification to that receipt would cause its hash to no longer match the leaf that was actually anchored — this is detectable by anyone who independently recomputes the Merkle proof against the on-chain root (DATA_MODEL.md §3.9, TESTING.md §10).

**Residual risk:** Records **not yet anchored** (`anchoring_status = unanchored`) have no on-chain tamper evidence yet — local-only tampering between issuance and the next anchoring batch is not detectable by the Merkle mechanism (ARCHITECTURE.md §10 explicitly notes anchoring is periodic, not per-record-instant). This is an inherent latency in any batched-anchoring design; more frequent anchoring reduces but does not eliminate this window. Also, a compromise of the Jetson itself (T7 below) could tamper with records *before* they're ever anchored, and no downstream mechanism described here would catch that specific record.

### T6 — Replayed payments

**Description:** An attacker attempts to reuse a previously valid `X-PAYMENT` payload to obtain a second semantic-repair call without paying again, or an agent double-submits and is unintentionally charged twice for what should be one request.

**Mitigation:** Payment verification and settlement is delegated to the GoPlausible AVM facilitator and Algorand network (ARCHITECTURE.md §5.1), which are responsible for standard payment-replay protection at the protocol level (transaction uniqueness on Algorand). On Verified's side, `PaymentMetadata.x402_challenge_ref` correlates a specific 402 challenge to its payment attempt (DATA_MODEL.md §3.5), which should prevent an old payment from being accepted against a new, unrelated challenge.

**Residual risk:** The *request-level* replay/idempotency question (an agent resubmitting the same verification request and whether that should reuse a receipt or trigger a fresh, separately-charged escalation) is explicitly marked TBD in DESIGN.md §7 and not yet a finalized decision — until resolved, there is a risk of either unintended double-charging (poor UX/trust) or unintended free re-verification (abuse potential), depending on which default is implemented. This should be prioritized in Milestone 0/TASKS.md before the demo, since it's a plausible judge question.

### T7 — Compromised local components (Jetson-level compromise)

**Description:** An attacker gains code-execution or file-system access on the Jetson itself, potentially able to alter validation logic, bypass the privacy filter, exfiltrate raw payloads, or forge unanchored records.

**Mitigation:** Architecturally, this is why anchoring exists at all (Architecture Principle 7/Principle 6) — once anchored, tampering is detectable. The privacy filter and validation stages are designed as pure/stateless contracts (DESIGN.md §4) with no unnecessary persistent unfiltered payload storage beyond the local record (which is not exposed externally except via the filtered escalation path, DESIGN.md §10).

**Residual risk:** This threat model does not attempt to fully solve device-level compromise (e.g., no HSM/secure-enclave design, no attestation of the validator binary itself — validator_version is self-reported, not remotely attested). This is explicitly flagged as beyond hackathon MVP scope (PRD.md §10, Excluded: "production-grade key management / HSM integration") and a clear direction for future hardening (PRD.md §11).

### T8 — Data leakage via escalation

**Description:** Confidential payload content is exposed to the semantic-repair API, the facilitator, or (worst case) the Algorand ledger, beyond what is strictly necessary and intended.

**Mitigation:** Privacy Filter runs unconditionally before any escalation decision (ARCHITECTURE.md §4.4). Only the filtered/minimized payload is ever sent to the semantic-repair API (DESIGN.md §10). The facilitator and Algorand receive only payment-protocol data and Merkle roots respectively — never payload content (ARCHITECTURE.md §9, trust boundary diagram). Raw payloads are never placed on-chain under any circumstance (Architecture Principle 6, FR10 in PRD.md).

**Residual risk:** Effectiveness is bounded by the completeness of the privacy filter taxonomy (Milestone 0 TBD, ARCHITECTURE.md §4.4) — an under-specified taxonomy could miss a sensitive-content pattern not anticipated by the hackathon team. This is a known category of residual risk for any pattern/policy-based filter and should be scoped honestly in the demo narrative rather than overclaimed.

### T9 — Payment failures affecting availability/trust

**Description:** Legitimate agents experience payment failures (facilitator downtime, Algorand network congestion, insufficient funds) that block otherwise-legitimate semantic repair, or an attacker deliberately induces payment failures to cause denial of service against the escalation path.

**Mitigation:** Fail-closed design means payment failure results in a clean `rejected` receipt with explicit reason (DESIGN.md §9), not a hang or an unsafe fallback pass. This preserves system integrity even under adverse payment conditions — availability of the *paid* repair feature degrades gracefully into "no repair," not into "unsafe pass."

**Residual risk:** The local-only validation path remains available even if payment/escalation infrastructure is fully down, but any request that genuinely needs semantic repair is simply unavailable during an outage — this is an accepted trade-off of the fail-closed design (favoring safety over availability), consistent with Architecture Principle 8, and should be stated plainly rather than treated as a solvable problem within this scope.

### T10 — Malicious clients abusing the escalation path

**Description:** A client deliberately submits requests engineered to trigger semantic-repair escalation for outputs that don't actually need it, in order to extract value from the semantic-repair API (e.g., using Verified as a cheap proxy to an LLM-backed service) or to probe the system's behavior.

**Mitigation:** Escalation is only reachable for requests that have genuinely unresolved `blocking` findings after local validation and deterministic repair (ARCHITECTURE.md §4.1) — the client cannot directly request semantic repair without first producing output that fails local checks in a way classified as `repairable: semantic`. Each escalation is payment-gated (Architecture Principle 3), which imposes an economic cost on abuse.

**Residual risk:** A sufficiently motivated client could still deliberately craft "almost-valid" output specifically to route through semantic repair as a paid pass-through to the underlying LLM-backed service, since payment gates cost but not intent. This is a known limitation of pay-per-call gating as an abuse-prevention mechanism (it limits volume/cost of abuse, not eliminates the possibility) and is noted as a future-scope hardening area (e.g., rate limiting, anomaly detection on escalation patterns) rather than solved in the MVP.

### T11 — Algorand / audit integrity threats

**Description:** Threats specific to the anchoring mechanism: an attacker attempting to submit a false Merkle root, forge inclusion in an already-anchored root, or otherwise undermine the audit trail's integrity.

**Mitigation:** Merkle root anchoring transactions are submitted to and confirmed by the Algorand network itself, inheriting Algorand's consensus-level integrity guarantees for the anchored root's immutability once confirmed (ARCHITECTURE.md §8). Proof of inclusion is independently verifiable by anyone who can recompute the Merkle path against the confirmed on-chain root (DATA_MODEL.md §3.9) — this does not depend on trusting Verified's own record store after the fact.

**Residual risk:** Integrity of the *anchoring process itself* (i.e., that the Merkle tree Verified constructed prior to submission faithfully represents the actual local records, and wasn't already tampered with before anchoring — see T5/T7) is not something the Algorand anchor can itself prove; it can only prove that whatever root was submitted has not changed since. This is an inherent property of anchoring-based audit systems generally, not a Verified-specific flaw, but should be communicated accurately (anchoring proves non-tampering *after* anchoring, not correctness *at the moment of* anchoring).

## 4. Threats Explicitly Out of Scope for This Model

Consistent with PRD.md's Non-Goals and MVP scope:
- Physical security/tamper-resistance of the Jetson Nano hardware itself.
- Formal cryptographic proof/verification of the validator binary's integrity (remote attestation) — noted as a T7 gap, not solved here.
- Denial-of-service protection at the network-infrastructure level (rate limiting, DDoS mitigation) beyond what's noted in T10 as future scope.
- Wallet/key management security for the agent-side signing key — explicitly a PRD.md Non-Goal (Verified does not manage agent wallets).

## 5. Summary Table

| ID | Threat | Primary Mitigation | Key Residual Risk |
|---|---|---|---|
| T1 | Malicious AI output | Multi-stage structural validation, fail-closed | Rule-set coverage limits |
| T2 | Prompt-injection-derived output | Structural + privacy checks | No semantic-intent verification (scope boundary) |
| T3 | Unsafe SQL | Dedicated safety checker, no auto-rewrite | Rule-set/dialect coverage limits |
| T4 | Forged receipts | Hash binding | No signing in MVP unless resolved (TBD, flagged priority) |
| T5 | Tampered hashes/records | Merkle anchoring | Unanchored window; pre-anchor local compromise |
| T6 | Replayed payments | Facilitator/Algorand-level protection, challenge correlation | Request-level idempotency policy still TBD |
| T7 | Compromised local components | Stateless pipeline contracts, anchoring for tamper evidence | No HSM/attestation in MVP (explicit exclusion) |
| T8 | Data leakage via escalation | Unconditional privacy filter, minimized outward data | Filter taxonomy completeness |
| T9 | Payment failures | Fail-closed rejection | Availability trade-off, accepted by design |
| T10 | Malicious clients abusing escalation | Payment gating | Economic, not intent-based, deterrent |
| T11 | Algorand/audit integrity | Algorand consensus guarantees, independent proof verification | Only proves post-anchor integrity, not pre-anchor correctness |
