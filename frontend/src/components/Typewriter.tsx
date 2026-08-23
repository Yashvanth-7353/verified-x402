import { useEffect, useState, type ReactNode } from 'react';

export interface TypeSegment {
  text: string;
  className?: string;
}

const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Types out one or more styled segments in sequence, with a blinking caret.
 *  The whole animation (startDelay + typing) is capped at `maxDuration` —
 *  `speed` is a per-char upper bound that gets scaled down for longer text
 *  so it never runs past the cap. */
export function Typewriter({
  segments,
  speed = 32,
  startDelay = 200,
  maxDuration = 1500,
  as: Tag = 'span',
  className = '',
  onDone,
}: {
  segments: TypeSegment[];
  speed?: number;
  startDelay?: number;
  maxDuration?: number;
  as?: 'span' | 'h1' | 'h2' | 'p';
  className?: string;
  onDone?: () => void;
}) {
  const full = segments.map((s) => s.text).join('');
  const [count, setCount] = useState(reducedMotion ? full.length : 0);
  const [done, setDone] = useState(reducedMotion);

  useEffect(() => {
    if (reducedMotion) return;
    setCount(0);
    setDone(false);
    if (full.length === 0) {
      setDone(true);
      onDone?.();
      return;
    }

    // Frame-driven (not chained setTimeouts) so the reveal is paced by
    // elapsed wall-clock time each frame — immune to setTimeout drift/
    // throttling, which is what makes chained-timer typewriters feel
    // jittery instead of a smooth, evenly-paced sweep.
    const typingBudget = Math.max(1, maxDuration - startDelay);
    const perCharDuration = Math.min(speed, typingBudget / full.length);
    const totalTypingDuration = perCharDuration * full.length;

    let raf = 0;
    let cancelled = false;
    const start = performance.now() + startDelay;

    const frame = (now: number) => {
      if (cancelled) return;
      const elapsed = now - start;
      if (elapsed < 0) {
        raf = requestAnimationFrame(frame);
        return;
      }
      const next = Math.min(full.length, Math.ceil((elapsed / totalTypingDuration) * full.length));
      setCount(next);
      if (next >= full.length) {
        setDone(true);
        onDone?.();
        return;
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
    // Re-run only if the target text actually changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [full, speed, startDelay, maxDuration]);

  const { nodes: rendered } = segments.reduce<{ nodes: ReactNode[]; remaining: number }>(
    (acc, seg, i) => {
      const take = Math.max(0, Math.min(seg.text.length, acc.remaining));
      acc.nodes.push(
        <span key={i} className={seg.className}>
          {seg.text.slice(0, take)}
        </span>,
      );
      return { nodes: acc.nodes, remaining: acc.remaining - take };
    },
    { nodes: [], remaining: count },
  );

  return (
    <Tag className={className} style={{ position: 'relative', display: 'inline-block' }}>
      <span style={{ visibility: 'hidden', pointerEvents: 'none' }}>
        {segments.map((seg, i) => (
          <span key={i} className={seg.className}>{seg.text}</span>
        ))}
      </span>
      <span style={{ position: 'absolute', inset: 0, pointerEvents: 'none', textAlign: 'left', whiteSpace: 'pre-wrap' }}>
        {rendered}
        <span className={`type-caret ${done ? 'type-caret-done' : ''}`} aria-hidden="true" />
      </span>
      <span className="sr-only">{full}</span>
    </Tag>
  );
}
