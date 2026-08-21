import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API_BASE, health } from '../api/client';
import { Logo } from './Logo';

export function Footer() {
  const [up, setUp] = useState<'checking' | 'up' | 'down'>('checking');

  useEffect(() => {
    let cancelled = false;
    health()
      .then(() => !cancelled && setUp('up'))
      .catch(() => !cancelled && setUp('down'));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <a href="/" className="footer-brand" style={{ marginBottom: 10 }}>
              <Logo size={24} />
              Verified
            </a>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 260, marginTop: 10 }}>
              A notarial layer for AI-agent structured output — validated, repaired, re-validated, signed, and
              anchored to Algorand.
            </p>
          </div>

          <div className="footer-col">
            <h4>Product</h4>
            <Link to="/verify">Verify an output</Link>
            <Link to="/history">History</Link>
            <Link to="/anchoring">Anchoring</Link>
          </div>

          <div className="footer-col">
            <h4>Proof</h4>
            <Link to="/verify-receipt">Verify a receipt</Link>
            <Link to="/about">Architecture</Link>
          </div>

          <div className="footer-col">
            <h4>System</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', fontSize: 13.5, color: 'var(--text-muted)' }}>
              <span className={`status-dot ${up === 'up' ? 'live' : up === 'down' ? 'down' : ''}`} />
              {up === 'checking' ? 'Checking backend…' : up === 'up' ? 'Backend reachable' : 'Backend unreachable'}
            </div>
            <span className="mono" style={{ display: 'block', padding: '5px 0', fontSize: 12, color: 'var(--text-faint)' }}>
              {API_BASE}
            </span>
          </div>
        </div>

        <div className="footer-base">
          <span>No valid proof, no execution.</span>
          <span>Local-first · fail-closed · Algorand TestNet</span>
        </div>
      </div>
    </footer>
  );
}
