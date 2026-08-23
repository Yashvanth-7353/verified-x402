/**
 * Four curated example payloads that exercise distinct real backend code paths.
 *
 * All examples are INPUT-ONLY. The backend determines the actual result.
 * No operational output is mocked or hardcoded.
 *
 * - "valid": complete, correctly-typed invoice → verified immediately, free.
 * - "deterministic": string types where integers/numbers expected →
 *   deterministic repair (coercion) → free.
 * - "missingField": null value for a required field with no schema default →
 *   deterministic repair cannot help → escalation to /semantic-repair
 *   → x402 payment → Groq → re-validation.
 * - "businessRule": mathematically inconsistent grand_total →
 *   deterministic repair cannot reason about arithmetic →
 *   escalation to semantic repair → payment → Groq → re-validation.
 */

export interface Example {
  id: string;
  label: string;
  /** Short real-world scenario description */
  description: string;
  /** Short hint shown on the example card */
  hint: string;
  /** Category badge text */
  category: 'VALID' | 'DETERMINISTIC' | 'SEMANTIC';
  /** Visual indicator: pass, warn, or fail */
  indicator: 'pass' | 'warn' | 'fail';
  outputType: 'json';
  schemaRef: string;
  schemaVersion: string;
  schemaDefinition: Record<string, unknown>;
  payload: Record<string, unknown>;
  /** Optional business rules for the schema policy */
  businessRules?: Array<Record<string, unknown>>;
}

// ---------------------------------------------------------------------------
// Schema: Invoice (all fields present, correct types)
// ---------------------------------------------------------------------------

const INVOICE_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    invoice_id: { type: 'string' },
    customer: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        email: { type: 'string' },
      },
      required: ['name', 'email'],
    },
    currency: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          description: { type: 'string' },
          quantity: { type: 'integer' },
          unit_price: { type: 'number' },
        },
        required: ['description', 'quantity', 'unit_price'],
      },
    },
    subtotal: { type: 'number' },
    tax: { type: 'number' },
    total: { type: 'number' },
  },
  required: ['invoice_id', 'customer', 'currency', 'items', 'subtotal', 'tax', 'total'],
};

// ---------------------------------------------------------------------------
// Schema: Purchase Order (quantity → integer, unit_price → number)
// ---------------------------------------------------------------------------

const PURCHASE_ORDER_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    purchase_order_id: { type: 'string' },
    supplier: { type: 'string' },
    currency: { type: 'string' },
    quantity: { type: 'integer' },
    unit_price: { type: 'number' },
    priority: { type: 'string' },
  },
  required: ['purchase_order_id', 'supplier', 'currency', 'quantity', 'unit_price', 'priority'],
};

// ---------------------------------------------------------------------------
// Schema: Support Ticket (recommended_action required, no default)
// ---------------------------------------------------------------------------

const SUPPORT_TICKET_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    ticket_id: { type: 'string' },
    customer: { type: 'string' },
    issue: { type: 'string' },
    severity: { type: 'string' },
    recommended_action: { type: 'string' },
  },
  required: ['ticket_id', 'customer', 'issue', 'severity', 'recommended_action'],
};

// ---------------------------------------------------------------------------
// Schema: Financial Report
// ---------------------------------------------------------------------------

const FINANCIAL_REPORT_SCHEMA: Record<string, unknown> = {
  type: 'object',
  properties: {
    report_id: { type: 'string' },
    customer: { type: 'string' },
    currency: { type: 'string' },
    line_items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          description: { type: 'string' },
          quantity: { type: 'integer' },
          unit_price: { type: 'number' },
          total: { type: 'number' },
        },
        required: ['description', 'quantity', 'unit_price', 'total'],
      },
    },
    subtotal: { type: 'number' },
    discount: { type: 'number' },
    tax: { type: 'number' },
    grand_total: { type: 'number' },
  },
  required: ['report_id', 'customer', 'currency', 'line_items', 'subtotal', 'discount', 'tax', 'grand_total'],
};

// ---------------------------------------------------------------------------
// Examples
// ---------------------------------------------------------------------------

export const EXAMPLES: Example[] = [
  {
    id: 'valid',
    label: 'AI-Generated Invoice',
    description:
      'A billing agent generated a structurally and semantically valid invoice. All fields are present and correctly typed.',
    hint: 'Already valid — no repair required',
    category: 'VALID',
    indicator: 'pass',
    outputType: 'json',
    schemaRef: 'invoice.v1',
    schemaVersion: '1.0',
    schemaDefinition: INVOICE_SCHEMA,
    payload: {
      invoice_id: 'INV-2026-08421',
      customer: {
        name: 'Acme Robotics',
        email: 'finance@acmerobotics.com',
      },
      currency: 'USD',
      items: [
        {
          description: 'Industrial Vision Sensor',
          quantity: 4,
          unit_price: 1250,
        },
        {
          description: 'Installation Service',
          quantity: 1,
          unit_price: 600,
        },
      ],
      subtotal: 5600,
      tax: 560,
      total: 6160,
    },
  },
  {
    id: 'deterministic',
    label: 'AI Purchase Order',
    description:
      'A procurement agent sent quantity and unit_price as strings instead of numbers. Deterministic repair coerces them to the correct types.',
    hint: 'Deterministic type correction — no payment',
    category: 'DETERMINISTIC',
    indicator: 'warn',
    outputType: 'json',
    schemaRef: 'purchase-order.v1',
    schemaVersion: '1.0',
    schemaDefinition: PURCHASE_ORDER_SCHEMA,
    payload: {
      purchase_order_id: 'PO-48291',
      supplier: 'Acme Robotics',
      currency: 'USD',
      quantity: '50',
      unit_price: '125.50',
      priority: 'standard',
    },
  },
  {
    id: 'missingField',
    label: 'AI Support Agent',
    description:
      'A support agent omitted the recommended_action — the schema requires it with no default. Deterministic repair cannot infer a meaningful value; semantic repair is needed.',
    hint: 'Missing meaningful information — semantic repair',
    category: 'SEMANTIC',
    indicator: 'warn',
    outputType: 'json',
    schemaRef: 'support-ticket.v1',
    schemaVersion: '1.0',
    schemaDefinition: SUPPORT_TICKET_SCHEMA,
    payload: {
      ticket_id: 'SUP-93821',
      customer: 'Global Manufacturing Ltd',
      issue: 'Production line stopped after sensor replacement',
      severity: 'high',
      recommended_action: null,
    },
  },
  {
    id: 'businessRule',
    label: 'AI Financial Report',
    description:
      'A reporting agent generated a grand_total of 14750, but the correct value is 13750 (13500 − 1000 + 1250). Deterministic repair cannot evaluate arithmetic; semantic reasoning is required.',
    hint: 'Business-rule inconsistency — semantic repair',
    category: 'SEMANTIC',
    indicator: 'warn',
    outputType: 'json',
    schemaRef: 'financial-report.v1',
    schemaVersion: '1.0',
    schemaDefinition: FINANCIAL_REPORT_SCHEMA,
    payload: {
      report_id: 'FIN-Q3-2026-018',
      customer: 'Acme Robotics',
      currency: 'USD',
      line_items: [
        {
          description: 'Hardware',
          quantity: 10,
          unit_price: 1200,
          total: 12000,
        },
        {
          description: 'Installation',
          quantity: 2,
          unit_price: 750,
          total: 1500,
        },
      ],
      subtotal: 13500,
      discount: 1000,
      tax: 1250,
      grand_total: 14750,
    },
    businessRules: [
      {
        type: 'financial_consistency',
        description: 'grand_total must equal (subtotal − discount) + tax',
        computed_field: 'grand_total',
        formula: {
          operands: ['subtotal', 'discount', 'tax'],
          expression: 'subtotal - discount + tax',
        },
      },
    ],
  },
];
