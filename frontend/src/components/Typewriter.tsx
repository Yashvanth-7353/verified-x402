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
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;

    const typingBudget = Math.max(0, maxDuration - startDelay);
    const effectiveSpeed = full.length > 0 ? Math.min(speed, typingBudget / full.length) : speed;

    const tick = () => {
      i += 1;
      setCount(i);
      if (i >= full.length) {
        setDone(true);
        onDone?.();
        return;
      }
      timer = setTimeout(tick, effectiveSpeed);
    };

    const startTimer = setTimeout(tick, startDelay);
    return () => {
      clearTimeout(startTimer);
      clearTimeout(timer);
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
