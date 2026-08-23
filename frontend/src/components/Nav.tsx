import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useWallet } from '@txnlab/use-wallet-react';
import { Logo } from './Logo';
import { MenuIcon, XIcon } from './icons';

const LINKS = [
  { to: '/', label: 'Dashboard' },
  { to: '/verify', label: 'Verify' },
  { to: '/history', label: 'History' },
  { to: '/anchoring', label: 'Anchoring' },
  { to: '/verify-receipt', label: 'Verify Receipt' },
  { to: '/about', label: 'About' },
];

function truncateAddr(addr: string): string {
  if (!addr || addr.length < 12) return addr ?? '';
  return `${addr.slice(0, 4)}…${addr.slice(-4)}`;
}

function isLinkActive(pathname: string, link: (typeof LINKS)[number]): boolean {
  // Use exact matching for all routes to avoid prefix collisions
  // (e.g., /verify would incorrectly match /verify-receipt)
  return pathname === link.to;
}

/** Scroll range (px) over which the header collapses — progress is scrubbed 1:1 with scroll position within it. */
const NAV_COLLAPSE_RANGE = 140;

export function Nav() {
  const [open, setOpen] = useState(false);
  const [progress, setProgress] = useState(0);
  const scrolled = progress > 0;
  const collapsed = progress >= 1;
  const location = useLocation();
  const activeIndex = LINKS.findIndex((l) => isLinkActive(location.pathname, l));

  // Wallet
  const { activeAddress, activeWallet, wallets, isReady } = useWallet();
  const [walletMenuOpen, setWalletMenuOpen] = useState(false);

  const onConnect = async () => {
    if (!isReady || !wallets.length) return;
    const pera = wallets.find((w) => w.id === 'pera');
    if (pera) await pera.connect();
  };

  const onDisconnect = async () => {
    if (activeWallet) {
      await activeWallet.disconnect();
      setWalletMenuOpen(false);
    }
  };

  const copyAddress = async () => {
    if (activeAddress) {
      await navigator.clipboard.writeText(activeAddress);
    }
  };

  const linkRefs = useRef<Array<HTMLAnchorElement | null>>([]);
  const [pillStyle, setPillStyle] = useState<{ transform: string; width: number; opacity: number }>({
    transform: 'translateX(0px)',
    width: 0,
    opacity: 0,
  });

  useLayoutEffect(() => {
    const el = linkRefs.current[activeIndex];
    if (!el) {
      setPillStyle((s) => ({ ...s, opacity: 0 }));
      return;
    }
    setPillStyle({ transform: `translateX(${el.offsetLeft}px)`, width: el.offsetWidth, opacity: 1 });
  }, [activeIndex, scrolled]);

  useEffect(() => {
    let raf = 0;
    const computeProgress = () => Math.min(1, Math.max(0, window.scrollY / NAV_COLLAPSE_RANGE));
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        setProgress(computeProgress());
      });
    };
    setProgress(computeProgress());
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, []);

  const handleLinkClick = (to: string) => {
    setOpen(false);
    if (location.pathname === to || (to === '/' && location.pathname === '')) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  return (
    <div className="dock-wrap">
      <div
        className={`dock-row ${scrolled ? 'nav-scrolled' : ''} ${collapsed ? 'nav-collapsed' : ''}`}
        style={{ ['--nav-progress' as string]: progress }}
      >
        <Link
          to="/"
          className="dock-brand glass-strong"
          aria-label="Verified — home"
          onClick={() => handleLinkClick('/')}
        >
          <Logo size={26} />
          <span className="dock-brand-text">Verified</span>
        </Link>

        <nav className="dock-nav glass-strong" aria-label="Primary">
          <span className="dock-pill" style={pillStyle} />
          {LINKS.map((l, i) => (
            <Link
              key={l.to}
              to={l.to}
              ref={(el) => {
                linkRefs.current[i] = el;
              }}
              onClick={() => handleLinkClick(l.to)}
              className={`dock-link ${i === activeIndex ? 'active' : ''}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        {/* Wallet section */}
        <div className="dock-wallet" style={{ display: 'flex', alignItems: 'center', gap: 8, pointerEvents: 'auto' }}>
          {activeAddress ? (
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                className="glass-strong"
                onClick={() => setWalletMenuOpen((v) => !v)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.85)',
                  background: 'rgba(255,255,255,0.72)', backdropFilter: 'blur(28px) saturate(190%)',
                  cursor: 'pointer', fontSize: 12, fontWeight: 600, fontFamily: 'var(--mono)',
                  color: 'var(--text)',
                }}
              >
                <span className="status-dot live" style={{ width: 6, height: 6 }} />
                <span style={{ fontSize: 12 }}>{truncateAddr(activeAddress)}</span>
              </button>
              {walletMenuOpen && (
                <div
                  className="glass-strong"
                  style={{
                    position: 'absolute', top: '100%', right: 0, marginTop: 6,
                    minWidth: 280, padding: 8, borderRadius: 12,
                    border: '1px solid rgba(255,255,255,0.9)',
                    boxShadow: '0 16px 40px -10px rgba(20,22,14,0.18)',
                  }}
                >
                  <div style={{ padding: '6px 12px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-faint)' }}>
                    Algorand TestNet
                  </div>
                  <button
                    type="button"
                    onClick={copyAddress}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left',
                      padding: '8px 12px', border: 'none', background: 'transparent',
                      cursor: 'pointer', fontSize: 12, fontFamily: 'var(--mono)',
                      wordBreak: 'break-all', color: 'var(--text)',
                    }}
                  >
                    {activeAddress}
                  </button>
                  <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                  <button
                    type="button"
                    onClick={onDisconnect}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left',
                      padding: '8px 12px', border: 'none', background: 'transparent',
                      cursor: 'pointer', fontSize: 13, color: 'var(--danger)',
                    }}
                  >
                    Disconnect
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              type="button"
              onClick={onConnect}
              className="glass-strong"
              style={{
                padding: '7px 14px', borderRadius: 999,
                border: '1px solid rgba(255,255,255,0.85)',
                background: 'rgba(255,255,255,0.72)',
                backdropFilter: 'blur(28px) saturate(190%)',
                cursor: 'pointer', fontSize: 12, fontWeight: 600,
                color: 'var(--text)', transition: 'background 200ms',
              }}
            >
              Connect Wallet
            </button>
          )}
        </div>

        <button
          type="button"
          className="dock-toggle glass-strong"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="Toggle navigation"
        >
          {open ? <XIcon /> : <MenuIcon />}
        </button>
      </div>

      {open && (
        <div className="dock-sheet glass-strong">
          {LINKS.map((l, i) => (
            <Link
              key={l.to}
              to={l.to}
              onClick={() => handleLinkClick(l.to)}
              className={`dock-link ${i === activeIndex ? 'active' : ''}`}
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {l.label}
            </Link>
          ))}
          <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
          {activeAddress ? (
            <>
              <div style={{ padding: '8px 16px', fontSize: 11, color: 'var(--text-faint)' }}>
                {truncateAddr(activeAddress)}
              </div>
              <button type="button" className="dock-link" onClick={onDisconnect} style={{ color: 'var(--danger)' }}>
                Disconnect Wallet
              </button>
            </>
          ) : (
            <button type="button" className="dock-link" onClick={onConnect}>
              Connect Wallet
            </button>
          )}
        </div>
      )}
    </div>
  );
}
