import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { EmptyState } from '../components/Feedback';
import { HashChip } from '../components/Copyable';
import { OutcomeBadge } from '../components/StatusBadge';
import { formatDateTime } from '../lib/format';
import { clearSessionLog, loadSessionLog } from '../lib/session';

type Filter = 'all' | 'verified' | 'verified_repaired' | 'rejected';

export function History() {
  const [log, setLog] = useState(() => loadSessionLog());
  const [filter, setFilter] = useState<Filter>('all');
  const navigate = useNavigate();

  const filtered = useMemo(() => (filter === 'all' ? log : log.filter((e) => e.outcome === filter)), [log, filter]);

  return (
    <div className="page">
      <div className="container">
        <div className="copy-row" style={{ marginBottom: 4 }}>
          <h1 className="page-title" style={{ marginBottom: 0 }}>History</h1>
          {log.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                clearSessionLog();
                setLog([]);
              }}
            >
              Clear this list
            </button>
          )}
        </div>
        <p style={{ color: 'var(--text-muted)', marginBottom: 20, maxWidth: 640 }}>
          Verified's backend doesn't currently expose a server-side history endpoint (only <code className="mono">/verify</code>,{' '}
          <code className="mono">/semantic-repair</code>, <code className="mono">/anchor</code>, and{' '}
          <code className="mono">/receipt/*</code> exist). This is a record of verifications run from{' '}
          <em>this browser</em>, kept locally — not a claim about everything the server has processed.
        </p>

        {log.length > 0 && (
          <div className="tag-row" style={{ marginBottom: 18 }}>
            {(['all', 'verified', 'verified_repaired', 'rejected'] as Filter[]).map((f) => (
              <button
                key={f}
                type="button"
                className="btn btn-sm"
                onClick={() => setFilter(f)}
                style={{
                  background: filter === f ? 'var(--text)' : 'transparent',
                  color: filter === f ? '#fff' : 'var(--text)',
                  border: '1px solid var(--border-strong)',
                }}
              >
                {f === 'all' ? 'All' : f.replace('_', ' ')}
              </button>
            ))}
          </div>
        )}

        {log.length === 0 ? (
          <EmptyState
            title="No verifications yet"
            message="Run a verification and it will show up here."
            action={
              <Link to="/verify" className="btn btn-accent">
                Verify an output
              </Link>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState title="Nothing matches this filter" message="Try a different outcome filter." />
        ) : (
          <div className="card" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                  {['Agent', 'Request', 'Outcome', 'Receipt', 'When'].map((h) => (
                    <th key={h} style={{ padding: '12px 16px', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-faint)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="stagger-children">
                {filtered.map((e) => (
                  <tr
                    key={e.receipt_id}
                    onClick={() => navigate('/verify-receipt', { state: { receipt: e.receipt } })}
                    style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                  >
                    <td style={{ padding: '12px 16px', fontSize: 13.5 }}>{e.agent_identifier}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <HashChip value={e.request_id} head={8} tail={4} />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <OutcomeBadge outcome={e.outcome} />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <HashChip value={e.receipt_hash} head={8} tail={4} />
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: 12.5, color: 'var(--text-faint)' }}>{formatDateTime(e.logged_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
