/** Animated wordmark: seal ring draws in on mount, checkmark follows, gentle idle breathing. */
export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" className="logo-mark" role="img" aria-label="Verified logo">
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#3346e8" />
          <stop offset="100%" stopColor="#1a2a9e" />
        </linearGradient>
      </defs>
      <circle className="logo-ring-inner" cx="20" cy="20" r="17" fill="none" stroke="url(#logo-grad)" strokeWidth="2.6" opacity="0.16" />
      <circle className="logo-ring" cx="20" cy="20" r="17" fill="none" stroke="url(#logo-grad)" strokeWidth="2.6" pathLength={1} />
      <path className="logo-check" d="M12,20.5 L17,26 L28,13.5" fill="none" stroke="url(#logo-grad)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" pathLength={1} />
    </svg>
  );
}
