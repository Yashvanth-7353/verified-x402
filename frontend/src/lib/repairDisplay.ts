/**
 * Display utilities for semantic repair results.
 *
 * These are presentation-only helpers. They do NOT affect hashing,
 * canonicalization, receipt generation, or any backend logic.
 */

/**
 * Reorder an object's keys to match the reference object's key order.
 * Keys present in `repaired` but not in `reference` are appended at the end.
 * Nested objects are recursively reordered.
 * Arrays are processed element-by-element.
 */
export function orderKeysByReference<T extends Record<string, unknown>>(
  reference: Record<string, unknown>,
  repaired: T,
): T {
  if (typeof reference !== 'object' || reference === null ||
      typeof repaired !== 'object' || repaired === null) {
    return repaired;
  }

  const ordered: Record<string, unknown> = {};
  const refKeys = Object.keys(reference);
  const repKeys = new Set(Object.keys(repaired));

  // First: keys in reference order
  for (const key of refKeys) {
    if (key in repaired) {
      const refVal = reference[key];
      const repVal = repaired[key];
      if (isPlainObject(refVal) && isPlainObject(repVal)) {
        ordered[key] = orderKeysByReference(refVal, repVal);
      } else if (Array.isArray(refVal) && Array.isArray(repVal)) {
        ordered[key] = orderArrayByReference(refVal, repVal);
      } else {
        ordered[key] = repVal;
      }
    }
    repKeys.delete(key);
  }

  // Then: remaining keys not in reference (preserve their original order)
  for (const key of Object.keys(repaired)) {
    if (repKeys.has(key)) {
      ordered[key] = repaired[key];
    }
  }

  return ordered as T;
}

function orderArrayByReference(
  refArr: unknown[],
  repArr: unknown[],
): unknown[] {
  return repArr.map((item, i) => {
    const refItem = refArr[i];
    if (isPlainObject(refItem) && isPlainObject(item)) {
      return orderKeysByReference(refItem, item);
    }
    return item;
  });
}

function isPlainObject(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

// ------------------------------------------------------------------
// Diff computation
// ------------------------------------------------------------------

export interface DiffEntry {
  path: string;
  before: unknown;
  after: unknown;
}

/**
 * Compute a flat list of changed leaf values between two objects.
 * Only reports paths where the actual value differs.
 */
export function computeDiff(
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): DiffEntry[] {
  const diffs: DiffEntry[] = [];
  collectDiffs(before, after, '', diffs);
  return diffs;
}

function collectDiffs(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
  prefix: string,
  out: DiffEntry[],
): void {
  const allKeys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of allKeys) {
    const path = prefix ? `${prefix}.${key}` : key;
    const aVal = a[key];
    const bVal = b[key];

    if (isPlainObject(aVal) && isPlainObject(bVal)) {
      collectDiffs(aVal, bVal, path, out);
    } else if (JSON.stringify(aVal) !== JSON.stringify(bVal)) {
      out.push({ path, before: aVal, after: bVal });
    }
  }
}

/**
 * Format a diff entry for display.
 */
export function formatDiffValue(val: unknown): string {
  if (val === null) return 'null';
  if (val === undefined) return 'undefined';
  if (typeof val === 'string') return val;
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  return JSON.stringify(val);
}
