import { useEffect, useState, useRef } from 'react';

export function CustomCursor() {
  const [hovered, setHovered] = useState(false);
  const [clicked, setClicked] = useState(false);
  
  const innerRef = useRef<HTMLDivElement>(null);
  const outerRef = useRef<HTMLDivElement>(null);
  const requestRef = useRef<number>(0);
  
  const mouse = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
  const trailed = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouse.current = { x: e.clientX, y: e.clientY };
      
      const target = e.target as HTMLElement;
      if (target.closest('a, button, input, [role="button"], .btn')) {
        setHovered(true);
      } else {
        setHovered(false);
      }
    };

    const handleMouseDown = () => setClicked(true);
    const handleMouseUp = () => setClicked(false);

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mouseup', handleMouseUp);

    // Trailing time-constant in ms — the outer ring closes ~63% of the
    // remaining distance every TAU ms, regardless of frame rate. A fixed
    // per-frame lerp factor (the old approach) implicitly assumes 60fps:
    // on a 120Hz display it applies twice as often and trails noticeably
    // less, on a throttled/laggy tab it jumps in bigger steps — both read
    // as inconsistent motion. Deriving the factor from actual elapsed time
    // keeps the trail feeling identical everywhere.
    const TAU = 55;
    let lastTime = performance.now();

    const animate = (now: number) => {
      const dt = now - lastTime;
      lastTime = now;

      // Inner cursor instantly follows mouse
      if (innerRef.current) {
        innerRef.current.style.transform = `translate3d(${mouse.current.x}px, ${mouse.current.y}px, 0)`;
      }

      // Outer cursor trails slightly, eased by elapsed time not frame count
      const factor = 1 - Math.exp(-dt / TAU);
      trailed.current.x += (mouse.current.x - trailed.current.x) * factor;
      trailed.current.y += (mouse.current.y - trailed.current.y) * factor;

      if (outerRef.current) {
        outerRef.current.style.transform = `translate3d(${trailed.current.x}px, ${trailed.current.y}px, 0)`;
      }

      requestRef.current = requestAnimationFrame(animate);
    };
    requestRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mouseup', handleMouseUp);
      cancelAnimationFrame(requestRef.current);
    };
  }, []);

  return (
    <>
      <div
        ref={innerRef}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: 8,
          height: 8,
          marginLeft: -4,
          marginTop: -4,
          borderRadius: '50%',
          backgroundColor: hovered ? 'var(--seal)' : 'var(--accent)',
          pointerEvents: 'none',
          zIndex: 9999,
          willChange: 'transform',
          transition: 'background-color 0.3s ease',
          mixBlendMode: 'difference',
        }}
      />
      <div
        ref={outerRef}
        className={`custom-cursor-outer ${hovered ? 'hovered' : ''} ${clicked ? 'clicked' : ''}`}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: 40,
          height: 40,
          marginLeft: -20,
          marginTop: -20,
          borderRadius: '50%',
          border: `1.5px solid ${hovered ? 'var(--seal)' : 'var(--accent)'}`,
          pointerEvents: 'none',
          zIndex: 9998,
          willChange: 'transform',
          transition: 'border-color 0.3s ease, width 0.3s ease, height 0.3s ease, margin 0.3s ease',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {hovered && (
          <div
            style={{
              width: '100%',
              height: '100%',
              borderRadius: '50%',
              border: '1px dashed var(--seal)',
              animation: 'spin 4s linear infinite',
              opacity: 0.5,
            }}
          />
        )}
      </div>
    </>
  );
}
