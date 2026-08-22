/**
 * Curated example payloads that exercise real backend code paths — verified
 * against backend/app/validation/stages/schema.py and
 * backend/app/repair/{deterministic,semantic}.py:
 *
 * - "clean": passes schema validation as-is → verified.
 * - "defaulted": omits a field the schema declares a `default` for → the
 *   deterministic repair engine fills it in (schema_defaults rule) → verified_repaired.
 * - "needsRepair": omits a required field with no schema default — deterministic
 *   repair can't help. Escalation to /semantic-repair triggers x402 payment,
 *   then GroqSemanticProvider (production) or MockSemanticProvider (tests)
 *   generates a candidate repair, which is re-validated.
 */

export interface Example {
  id: string;
  label: string;
  description: string;
  outputType: 'json';
  schemaRef: string;
  schemaVersion: string;
  schemaDefinition: Record<string, unknown>;
  payload: Record<string, unknown>;
}

export const EXAMPLES: Example[] = [
  {
    id: 'clean',
    label: 'Clean output',
    description: 'Matches its schema exactly — passes on the first local pass, no repair needed.',
    outputType: 'json',
    schemaRef: 'invoice.v1',
    schemaVersion: '1.0',
    schemaDefinition: {
      type: 'object',
      properties: {
        customer: { type: 'string' },
        amount_usd: { type: 'number' },
      },
      required: ['customer', 'amount_usd'],
    },
    payload: { customer: 'Acme Robotics', amount_usd: 480 },
  },
  {
    id: 'defaulted',
    label: 'Missing field with a schema default',
    description: 'Omits "status", which the schema declares a default for — deterministic repair fills it, no payment.',
    outputType: 'json',
    schemaRef: 'invoice.v1',
    schemaVersion: '1.0',
    schemaDefinition: {
      type: 'object',
      properties: {
        customer: { type: 'string' },
        amount_usd: { type: 'number' },
        status: { type: 'string', default: 'pending' },
      },
      required: ['customer', 'amount_usd', 'status'],
    },
    payload: { customer: 'Acme Robotics', amount_usd: 480 },
  },
  {
    id: 'needsRepair',
    label: 'Requires semantic repair',
    description: 'Missing "amount_usd" with no default — deterministic repair can\'t help. Needs the paid semantic-repair escalation.',
    outputType: 'json',
    schemaRef: 'invoice.v1',
    schemaVersion: '1.0',
    schemaDefinition: {
      type: 'object',
      properties: {
        customer: { type: 'string' },
        amount_usd: { type: 'number' },
      },
      required: ['customer', 'amount_usd'],
    },
    payload: {
      customer: 'Acme Robotics',
      inject_mock_semantic_repair: { amount_usd: 480 },
    },
  },
];
