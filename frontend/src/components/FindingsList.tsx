import type { ValidationFinding } from '../api/types';
import { SeverityBadge } from './StatusBadge';

const REPAIRABLE_LABEL: Record<string, string> = {
  deterministic: 'Fixable deterministically',
  semantic: 'Requires semantic repair',
  not_repairable: 'Not repairable',
};

export function FindingsList({ findings }: { findings: ValidationFinding[] }) {
  if (findings.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '28px 16px' }}>
        <p>No findings — the output passed every check on the first pass.</p>
      </div>
    );
  }

  const byStage = new Map<string, ValidationFinding[]>();
  for (const f of findings) {
    const list = byStage.get(f.stage) ?? [];
    list.push(f);
    byStage.set(f.stage, list);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {[...byStage.entries()].map(([stage, items]) => (
        <div key={stage}>
          <div className="section-title">{stage.replace(/_/g, ' ')}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((f) => (
              <div
                key={f.finding_id}
                className="card"
                style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}
              >
                <div className="copy-row">
                  <SeverityBadge severity={f.severity} />
                  <span className="badge badge-pending">{REPAIRABLE_LABEL[f.repairable] ?? f.repairable}</span>
                </div>
                <p style={{ fontSize: 13.5 }}>{f.description}</p>
                {f.field_path && <span className="mono" style={{ fontSize: 12, color: 'var(--text-faint)' }}>field: {f.field_path}</span>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
