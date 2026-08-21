import type { ReactNode } from 'react';

export function ErrorBanner({ title, message }: { title: string; message: string }) {
  return (
    <div
      className="card card-pad"
      role="alert"
      style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-bg)', color: 'var(--danger)' }}
    >
      <strong style={{ display: 'block', marginBottom: 4 }}>{title}</strong>
      <span style={{ fontSize: 13.5 }}>{message}</span>
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{message}</p>
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span className="spinner spinner-dark" />
      <span style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>{label}</span>
    </div>
  );
}
