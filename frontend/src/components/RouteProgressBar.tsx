import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

/** A thin animated bar that sweeps across the top on every route change — the page-transition cue. */
export function RouteProgressBar() {
  const location = useLocation();
  const [active, setActive] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setActive(true);
    const t = setTimeout(() => setActive(false), 520);
    return () => clearTimeout(t);
  }, [location.pathname]);

  return (
    <div className={`route-progress ${active ? 'running' : ''}`} aria-hidden="true">
      <span className="route-progress-bar" />
    </div>
  );
}
