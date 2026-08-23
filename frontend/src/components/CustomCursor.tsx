import { useEffect, useRef } from 'react';

export function CustomCursor() {
  const cursorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate3d(${e.clientX}px, ${e.clientY}px, 0)`;
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    return () => window.removeEventListener('mousemove', onMouseMove);
  }, []);

  return (
    <div
      ref={cursorRef}
      style={{
        position: 'fixed',
        top: -30,
        left: -30,
        width: 60,
        height: 60,
        borderRadius: '50%',
        pointerEvents: 'none',
        zIndex: 9999,
        backdropFilter: 'blur(4px) brightness(1.1) contrast(1.2)',
        WebkitBackdropFilter: 'blur(4px) brightness(1.1) contrast(1.2)',
        border: '1.5px solid rgba(255, 255, 255, 0.5)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12), inset 0 0 12px rgba(255, 255, 255, 0.2)',
        transition: 'transform 0.05s linear',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'rgba(255, 255, 255, 0.8)' }} />
    </div>
  );
}
