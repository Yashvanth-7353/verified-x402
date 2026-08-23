import type { SVGProps } from 'react';

const base = (props: SVGProps<SVGSVGElement>) => ({
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.4,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  ...props,
});

export const CheckIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export const XIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const CopyIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <rect x="9" y="9" width="12" height="12" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

export const ExternalIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <path d="M15 3h6v6M10 14 21 3" />
  </svg>
);

export const MenuIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
);

export const BoltIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" />
  </svg>
);

export const PackageIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M21 8 12 3 3 8l9 5 9-5z" />
    <path d="M3 8v8l9 5 9-5V8" />
    <path d="M12 13v8" />
  </svg>
);

export const LinkIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M9 17H7a5 5 0 0 1 0-10h2" />
    <path d="M15 7h2a5 5 0 0 1 0 10h-2" />
    <path d="M8 12h8" />
  </svg>
);

export const PlugIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M9 2v6M15 2v6" />
    <path d="M6 8h12v4a6 6 0 0 1-12 0V8z" />
    <path d="M12 18v4" />
  </svg>
);

export const ClipboardIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <rect x="5" y="4" width="14" height="18" rx="2" />
    <path d="M9 2h6v4H9z" />
    <path d="M9 12h6M9 16h6" />
  </svg>
);

export const ScanCheckIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M4 8V6a2 2 0 0 1 2-2h2M4 16v2a2 2 0 0 0 2 2h2M20 8V6a2 2 0 0 0-2-2h-2M20 16v2a2 2 0 0 1-2 2h-2" />
    <path d="M8 12.5 10.5 15 16 9" />
  </svg>
);

export const WrenchIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M14.5 3.5a5 5 0 0 0-6.6 6l-6 6 3 3 6-6a5 5 0 0 0 6-6.6l-3.2 3.2-2.4-2.4 3.2-3.2z" />
  </svg>
);

export const RefreshIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M20 11a8 8 0 0 0-14.6-4.6M4 4v5h5" />
    <path d="M4 13a8 8 0 0 0 14.6 4.6M20 20v-5h-5" />
  </svg>
);

export const StampIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <path d="M9 4h6l1.5 5.5H7.5L9 4z" />
    <path d="M8 9.5h8v5a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-5z" />
    <path d="M4 20.5c1-1.6 2.4-1.6 3.2-.6.9 1 2.4 1 3.3 0 .9-1 2.3-1 3.2 0 .9 1 2.4 1 3.3 0 .8-1 2.2-1 3.2.6" />
  </svg>
);

export const AnchorGlyphIcon = (props: SVGProps<SVGSVGElement>) => (
  <svg {...base(props)}>
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v13" />
    <path d="M5 12H2a10 10 0 0 0 10 10 10 10 0 0 0 10-10h-3" />
    <path d="M8 9 12 12l4-3" />
  </svg>
);
