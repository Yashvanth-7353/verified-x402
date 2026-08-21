import type { CSSProperties, ReactNode } from 'react';
import { useReveal } from '../lib/useReveal';

export function Reveal({
  children,
  delay = 0,
  variant = 'up',
  as: Tag = 'div',
  className = '',
}: {
  children: ReactNode;
  delay?: number;
  variant?: 'up' | 'left' | 'right' | 'scale';
  as?: 'div' | 'section' | 'li';
  className?: string;
}) {
  const [nodeRef, inView] = useReveal<HTMLDivElement>();
  const variantClass = variant === 'up' ? '' : `sr-${variant}`;

  return (
    <Tag
      ref={nodeRef as never}
      className={`sr ${variantClass} ${inView ? 'in-view' : ''} ${className}`.trim()}
      style={{ '--sr-delay': `${delay}ms` } as CSSProperties}
    >
      {children}
    </Tag>
  );
}
