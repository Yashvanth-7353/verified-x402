/**
 * Four curated example payloads that exercise distinct real backend code paths.
 *
 * All examples are INPUT-ONLY. The backend determines the actual result.
 * No operational output is mocked or hardcoded.
 *
 * - "clean": all fields present and correct types → verified.
 * - "missingField": omits a required field with no schema default —
 *   deterministic repair can't help, escalation to /semantic-repair
 *   triggers x402 payment → Groq → re-validation.
 * - "typeCorrection": "age" is a string ("25") instead of integer (25) —
 *   type mismatch detected by schema validation, semantic repair may fix.
 * - "unrepairable": multiple incompatible values — demonstrates the system
 *   does not blindly trust the LLM.
 */

export interface Example {
  id: string;
  label: string;
  description: string;
  /** Short hint shown on the example card */
  hint: string;
  /** Visual indicator: checkmark, warning, or cross */
  indicator: 'pass' | 'warn' | 'fail';
  outputType: 'json';
  schemaRef: string;
  schemaVersion: string;
  schemaDefinition: Record<string, unknown>;
  payload: Record<string, unknown>;
}

const PERSON_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    name: { type: 'string' },
    email: { type: 'string' },
    age: { type: 'integer' },
    country: { type: 'string' },
  },
  required: ['name', 'email', 'age', 'country'],
};

export const EXAMPLES: Example[] = [
  {
    id: 'clean',
    label: 'Clean Output',
    hint: 'Already satisfies the schema',
    description:
      'A valid structured output with all required fields and correct types. Should pass validation on the first local pass with no repair needed.',
    indicator: 'pass',
    outputType: 'json',
    schemaRef: 'person.v1',
    schemaVersion: '1.0',
    schemaDefinition: PERSON_SCHEMA,
    payload: {
      name: 'Alice',
      email: 'alice@example.com',
      age: 28,
      country: 'India',
    },
  },
  {
    id: 'missingField',
    label: 'Missing Required Field',
    hint: 'Missing age — demonstrates paid semantic repair',
    description:
      'The "age" field is omitted and the schema declares no default for it. Deterministic repair cannot fill it — escalation to semantic repair (x402 payment → Groq → re-validation) is required.',
    indicator: 'warn',
    outputType: 'json',
    schemaRef: 'person.v1',
    schemaVersion: '1.0',
    schemaDefinition: PERSON_SCHEMA,
    payload: {
      name: 'Bob',
      email: 'bob@example.com',
      country: 'India',
    },
  },
  {
    id: 'typeCorrection',
    label: 'Type Correction',
    hint: 'age has the wrong type — demonstrates semantic repair',
    description:
      '"age" is a string ("25") instead of an integer (25). Schema validation detects the type mismatch. Semantic repair via Groq may produce a corrected candidate that is then re-validated.',
    indicator: 'warn',
    outputType: 'json',
    schemaRef: 'person.v1',
    schemaVersion: '1.0',
    schemaDefinition: PERSON_SCHEMA,
    payload: {
      name: 'Charlie',
      email: 'charlie@example.com',
      age: '25',
      country: 'India',
    },
  },
  {
    id: 'unrepairable',
    label: 'Unrepairable Output',
    hint: 'Multiple incompatible values — demonstrates rejection',
    description:
      'Contains multiple severe type violations: numeric name, non-email string, string age, and null country. Designed to demonstrate that the system does not blindly accept LLM-generated repairs.',
    indicator: 'fail',
    outputType: 'json',
    schemaRef: 'person.v1',
    schemaVersion: '1.0',
    schemaDefinition: PERSON_SCHEMA,
    payload: {
      name: 12345,
      email: 'not-an-email',
      age: 'unknown',
      country: null,
    },
  },
];
