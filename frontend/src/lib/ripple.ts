/** Event-delegated ripple feedback for any element with class "btn" — no per-button wiring needed. */
export function attachRippleListener(): () => void {
  const onPointerDown = (e: PointerEvent) => {
    const target = (e.target as HTMLElement | null)?.closest<HTMLElement>('.btn');
    if (!target || target.hasAttribute('disabled')) return;

    const rect = target.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 1.4;
    const span = document.createElement('span');
    span.className = 'ripple';
    span.style.width = `${size}px`;
    span.style.height = `${size}px`;
    span.style.left = `${e.clientX - rect.left - size / 2}px`;
    span.style.top = `${e.clientY - rect.top - size / 2}px`;
    target.appendChild(span);
    span.addEventListener('animationend', () => span.remove());
  };

  document.addEventListener('pointerdown', onPointerDown);
  return () => document.removeEventListener('pointerdown', onPointerDown);
}
