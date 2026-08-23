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

/** Scroll-linked parallax translateY, applied directly to the element's own
 *  style rather than through React state. Driving this via setState meant
 *  every scroll pixel forced a getBoundingClientRect() layout read *and* a
 *  re-render of the whole page component that owns the ref — with two of
 *  these hooks active on the same page, each scroll frame did two forced
 *  layouts interleaved with two re-renders, a textbook layout-thrash that
 *  made scrolling feel janky. Mutating the node's transform directly skips
 *  React entirely, so a scroll frame costs one layout read + one style
 *  write per hook, with no reconciliation in between. */
export function useParallax<T extends HTMLElement>(strength = 0.15) {
  const nodeRef = useRef<T | null>(null);

  useEffect(() => {
    const el = nodeRef.current;
    if (!el || reducedMotion) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const rect = el.getBoundingClientRect();
      const center = rect.top + rect.height / 2 - window.innerHeight / 2;
      el.style.transform = `translateY(${center * -strength}px)`;
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

  return nodeRef;
}
