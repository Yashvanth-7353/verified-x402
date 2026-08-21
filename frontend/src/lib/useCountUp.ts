import { useEffect, useRef, useState } from 'react';
import { useReveal } from './useReveal';

/** Counts a number up from 0 once the returned ref scrolls into view. */
export function useCountUp(target: number, duration = 900) {
  const [nodeRef, inView] = useReveal<HTMLElement>(0.4);
  const [value, setValue] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - t) * (1 - t);
      setValue(Math.round(eased * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, target, duration]);

  return [nodeRef, value] as const;
}
