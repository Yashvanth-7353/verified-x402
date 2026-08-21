import { useRef, type MouseEvent } from 'react';

const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Mouse-driven 3D tilt — sets --tx/--ty custom properties consumed by .tilt-card. */
export function useTilt<T extends HTMLElement>(maxDeg = 8) {
  const nodeRef = useRef<T | null>(null);

  const onMouseMove = (e: MouseEvent) => {
    if (reducedMotion) return;
    const el = nodeRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    el.style.setProperty('--ty', `${px * maxDeg * 2}deg`);
    el.style.setProperty('--tx', `${-py * maxDeg * 2}deg`);
  };

  const onMouseLeave = () => {
    const el = nodeRef.current;
    if (!el) return;
    el.style.setProperty('--tx', '0deg');
    el.style.setProperty('--ty', '0deg');
  };

  return { nodeRef, onMouseMove, onMouseLeave };
}
