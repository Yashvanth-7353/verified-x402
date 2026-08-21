import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Logo } from './Logo';
import { MenuIcon, XIcon } from './icons';

const LINKS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/verify', label: 'Verify' },
  { to: '/history', label: 'History' },
  { to: '/anchoring', label: 'Anchoring' },
  { to: '/verify-receipt', label: 'Verify Receipt' },
  { to: '/about', label: 'About' },
];

function isLinkActive(pathname: string, link: (typeof LINKS)[number]): boolean {
  return link.end ? pathname === link.to : pathname.startsWith(link.to);
}

export function Nav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const activeIndex = LINKS.findIndex((l) => isLinkActive(location.pathname, l));

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
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
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
      <div className={`dock-row ${scrolled ? 'nav-scrolled' : ''}`}>
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
        </div>
      )}
    </div>
  );
}
