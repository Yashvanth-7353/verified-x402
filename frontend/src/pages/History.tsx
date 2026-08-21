import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError, type RecordSummary, type VerificationReceipt } from '../api/types';
import { listRecords } from '../api/client';
import { EmptyState, ErrorBanner } from '../components/Feedback';
import { HashChip } from '../components/Copyable';
import { OutcomeBadge } from '../components/StatusBadge';
import { formatDateTime } from '../lib/format';
import { clearSessionLog, loadSessionLog, type SessionEntry } from '../lib/session';

type Filter = 'all' | 'verified' | 'verified_repaired' | 'rejected';
type Source = 'server' | 'session';

export function History() {
  const [source, setSource] = useState<Source>('server');
  const [filter, setFilter] = useState<Filter>('all');
  const navigate = useNavigate();

  // Server-side records
  const [serverRecords, setServerRecords] = useState<RecordSummary[]>([]);
  const [serverTotal, setServerTotal] = useState(0);
  const [serverLoading, setServerLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [serverPage, setServerPage] = useState(0);
  const PAGE_SIZE = 25;

  // Session records (localStorage)
  const [sessionLog, setSessionLog] = useState<SessionEntry[]>(() => loadSessionLog());

  useEffect(() => {
    if (source !== 'server') return;
    let cancelled = false;
    const load = async () => {
      setServerLoading(true);
      setServerError(null);
      try {
        const res = await listRecords(serverPage * PAGE_SIZE, PAGE_SIZE);
        if (!cancelled) {
          setServerRecords(res.records);
          setServerTotal(res.total);
        }
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 503) {
            setServerError('Server-side history is not available. This backend does not have the records endpoint configured.');
          } else {
            setServerError(e instanceof Error ? e.message : 'Failed to load records from server.');
          }
        }
      } finally {
        if (!cancelled) setServerLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [source, serverPage]);

  const filteredServer = useMemo(
    () => (filter === 'all' ? serverRecords : serverRecords.filter((r) => r.outcome === filter)),
    [serverRecords, filter],
  );

  const filteredSession = useMemo(
    () => (filter === 'all' ? sessionLog : sessionLog.filter((e) => e.outcome === filter)),
    [sessionLog, filter],
  );

  const totalPages = Math.ceil(serverTotal / PAGE_SIZE);

  const navigateToVerify = (receipt: VerificationReceipt) => {
    navigate('/verify-receipt', { state: { receipt } });
  };

  return (
    <div className="page">
      <div className="container">
        <div className="copy-row" style={{ marginBottom: 4 }}>
          <h1 className="page-title" style={{ marginBottom: 0 }}>History</h1>
          {source === 'session' && sessionLog.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                clearSessionLog();
                setSessionLog([]);
              }}
            >
              Clear session log
            </button>
          )}
        </div>

        {/* Source toggle */}
        <div className="tag-row" style={{ marginBottom: 12 }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setSource('server')}
            style={{
              background: source === 'server' ? 'var(--text)' : 'transparent',
              color: source === 'server' ? '#fff' : 'var(--text)',
              border: '1px solid var(--border-strong)',
            }}
          >
            Server records
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setSource('session')}
            style={{
              background: source === 'session' ? 'var(--text)' : 'transparent',
              color: source === 'session' ? '#fff' : 'var(--text)',
              border: '1px solid var(--border-strong)',
            }}
          >
            This browser session
          </button>
        </div>

        {source === 'server' && (
          <p style={{ color: 'var(--text-muted)', marginBottom: 16, maxWidth: 640, fontSize: 13.5 }}>
            Verification records persisted on the server by the backend.
            {serverTotal > 0 && <> Showing {filteredServer.length} of {serverTotal} total records.</>}
          </p>
        )}

        {source === 'session' && (
          <p style={{ color: 'var(--text-muted)', marginBottom: 16, maxWidth: 640, fontSize: 13.5 }}>
            Local browser-only record of verifications run from this tab.
            This data is not shared across browsers or after clearing localStorage.
          </p>
        )}

        {/* Outcome filter */}
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

        {/* Server source */}
        {source === 'server' && (
          <>
            {serverLoading && (
              <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className="spinner spinner-dark" />
                <span style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>Loading records from server…</span>
              </div>
            )}

            {serverError && <ErrorBanner title="Could not load server records" message={serverError} />}

            {!serverLoading && !serverError && serverRecords.length === 0 && (
              <EmptyState
                title="No server records yet"
                message="Run a verification against the backend and it will be persisted server-side."
                action={
                  <Link to="/verify" className="btn btn-accent">
                    Verify an output
                  </Link>
                }
              />
            )}

            {!serverLoading && !serverError && serverRecords.length > 0 && filteredServer.length === 0 && (
              <EmptyState title="Nothing matches this filter" message="Try a different outcome filter." />
            )}

            {!serverLoading && !serverError && filteredServer.length > 0 && (
              <>
                <div className="card" style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
                    <thead>
                      <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                        {['Outcome', 'Request', 'Receipt', 'Anchoring', 'When'].map((h) => (
                          <th key={h} style={{ padding: '12px 16px', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-faint)' }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="stagger-children">
                      {filteredServer.map((r) => (
                        <tr
                          key={r.record_id}
                          style={{ borderBottom: '1px solid var(--border)' }}
                        >
                          <td style={{ padding: '12px 16px' }}>
                            <OutcomeBadge outcome={r.outcome} />
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <HashChip value={r.request_id} head={8} tail={4} />
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <HashChip value={r.receipt_hash} head={8} tail={4} />
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <span className={`badge ${r.anchoring_status === 'anchored' ? 'badge-success' : 'badge-pending'}`}>
                              {r.anchoring_status}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', fontSize: 12.5, color: 'var(--text-faint)' }}>
                            {formatDateTime(r.created_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 16 }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={serverPage === 0}
                      onClick={() => setServerPage((p) => p - 1)}
                    >
                      Previous
                    </button>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', alignSelf: 'center' }}>
                      Page {serverPage + 1} of {totalPages}
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={serverPage >= totalPages - 1}
                      onClick={() => setServerPage((p) => p + 1)}
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Session source */}
        {source === 'session' && (
          <>
            {filteredSession.length === 0 && sessionLog.length === 0 && (
              <EmptyState
                title="No session verifications"
                message="Run a verification and it will appear here."
                action={
                  <Link to="/verify" className="btn btn-accent">
                    Verify an output
                  </Link>
                }
              />
            )}

            {sessionLog.length > 0 && filteredSession.length === 0 && (
              <EmptyState title="Nothing matches this filter" message="Try a different outcome filter." />
            )}

            {filteredSession.length > 0 && (
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
                    {filteredSession.map((e) => (
                      <tr
                        key={e.receipt_id}
                        onClick={() => navigateToVerify(e.receipt)}
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
          </>
        )}
      </div>
    </div>
  );
}
