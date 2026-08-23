import { useEffect, useState } from 'react';
import { Logo } from './Logo';

/** Upper bound on how long the splash can hold the page — a safety net for
 *  a slow/stalled font fetch, not a fixed delay. The splash dismisses as
 *  soon as fonts are actually ready, which on a normal connection is well
 *  under this. */
const MAX_WAIT_MS = 5000;

/** Blocks first paint of the app behind a brief branded splash until web
 *  fonts are ready (or MAX_WAIT_MS elapses), so the page never flashes
 *  fallback-font text before swapping to the real typefaces. */
export function Preloader({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const done = () => {
      if (!cancelled) setReady(true);
    };

    const fontsReady = typeof document !== 'undefined' && 'fonts' in document
      ? document.fonts.ready
      : Promise.resolve();
    const timeout = new Promise<void>((resolve) => setTimeout(resolve, MAX_WAIT_MS));

    Promise.race([fontsReady, timeout]).then(done);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    const t = setTimeout(() => setVisible(false), 320);
    return () => clearTimeout(t);
  }, [ready]);

  return (
    <>
      {visible && (
        <div className={`preloader ${ready ? 'preloader-out' : ''}`} aria-hidden="true">
          <div className="preloader-mark">
            <Logo size={40} />
          </div>
        </div>
      )}
      {children}
    </>
  );
}
