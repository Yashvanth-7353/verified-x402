import type { VerificationOutcome } from '../api/types';

const WORD: Record<VerificationOutcome, string> = {
  verified: 'VERIFIED',
  verified_repaired: 'REPAIRED · VERIFIED',
  rejected: 'REJECTED',
};

const TONE: Record<VerificationOutcome, string> = {
  verified: '',
  verified_repaired: 'tone-repaired',
  rejected: 'tone-rejected',
};

/**
 * The one signature visual element: a notary-style engraved seal stamped
 * onto the result. A checkmark for pass outcomes, a broken mark for reject.
 */
export function VerificationSeal({ outcome, size = 112 }: { outcome: VerificationOutcome; size?: number }) {
  const teeth = 24;
  const rOuter = 46;
  const rInner = 40;
  const points: string[] = [];
  for (let i = 0; i < teeth * 2; i++) {
    const r = i % 2 === 0 ? rOuter : rOuter - 4;
    const a = (Math.PI * i) / teeth;
    points.push(`${50 + r * Math.cos(a)},${50 + r * Math.sin(a)}`);
  }

  return (
    <div className={`seal ${TONE[outcome]}`} style={{ width: size, height: size }} role="img" aria-label={`Seal: ${WORD[outcome]}`}>
      <svg viewBox="0 0 100 100">
        <polygon className="seal-teeth" points={points.join(' ')} />
        <circle className="seal-ring" cx="50" cy="50" r={rInner} strokeWidth="1.4" />
        <circle className="seal-ring" cx="50" cy="50" r={rInner - 6} strokeWidth="0.7" opacity="0.6" />

        <path
          id={`seal-arc-${outcome}`}
          d="M 20,58 A 30,30 0 1,1 80,58"
          fill="none"
          opacity="0"
        />
        <text className="seal-word">
          <textPath href={`#seal-arc-${outcome}`} startOffset="50%" textAnchor="middle">
            {WORD[outcome]}
          </textPath>
        </text>

        {outcome === 'rejected' ? (
          <path className="seal-mark" d="M40,40 L60,60 M60,40 L40,60" pathLength={40} />
        ) : (
          <path className="seal-mark" d="M35,51 L45,61 L66,38" pathLength={40} />
        )}
      </svg>
    </div>
  );
}

/** Sparing decorative texture — hero sections only. */
export function Guilloche() {
  const rings = Array.from({ length: 14 }, (_, i) => 40 + i * 26);
  return (
    <svg className="guilloche" viewBox="0 0 600 400" preserveAspectRatio="xMaxYMin slice" aria-hidden="true">
      <defs>
        <radialGradient id="gfade" cx="80%" cy="10%" r="75%">
          <stop offset="0%" stopColor="#263ee0" stopOpacity="0.16" />
          <stop offset="100%" stopColor="#263ee0" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="600" height="400" fill="url(#gfade)" />
      {rings.map((r) => (
        <circle key={r} cx="520" cy="10" r={r} fill="none" stroke="#263ee0" strokeWidth="0.6" opacity="0.22" />
      ))}
    </svg>
  );
}
