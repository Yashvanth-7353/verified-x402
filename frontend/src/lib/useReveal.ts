import { useEffect, useRef, useState } from 'react';

const supportsObserver = typeof IntersectionObserver !== 'undefined';

/** Adds `in-view` once an element crosses into the viewport (fires once). */
export function useReveal<T extends HTMLElement>(threshold = 0.16) {
  const nodeRef = useRef<T | null>(null);
  const [inView, setInView] = useState(!supportsObserver);

  useEffect(() => {
    const el = nodeRef.current;
    if (!el || !supportsObserver) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin: '0px 0px -8% 0px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return [nodeRef, inView] as const;
}

const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Scroll-linked parallax offset for an element, expressed as a translateY in px. */
export function useParallax<T extends HTMLElement>(strength = 0.15) {
  const nodeRef = useRef<T | null>(null);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const el = nodeRef.current;
    if (!el || reducedMotion) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const rect = el.getBoundingClientRect();
      const center = rect.top + rect.height / 2 - window.innerHeight / 2;
      setOffset(center * -strength);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [strength]);

  return [nodeRef, offset] as const;
}
