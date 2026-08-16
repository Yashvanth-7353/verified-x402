# Verified

Verified is a local-first structured-output verification layer for AI agents.

It validates, repairs, and verifies AI-generated structured outputs before execution.

## Architecture

AI Agent
→ Verified
→ Local Validation
→ Deterministic Repair
→ Semantic Repair via x402 when required
→ Revalidation
→ Verification Receipt
→ Algorand-backed Audit

## Project Structure

- `backend/` — FastAPI backend and verification engine
- `frontend/` — React dashboard
- `demo-agent/` — Agent integration/demo
- `docs/` — Project architecture and development documentation
- `scripts/` — Development and deployment scripts