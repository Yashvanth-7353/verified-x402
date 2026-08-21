import { useCallback, useRef, useState, type ReactNode } from 'react';
import { CheckIcon, XIcon } from '../components/icons';
import { ToastContext, type ToastItem } from './toastContext';

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const show = useCallback((message: string, tone: ToastItem['tone'] = 'accent') => {
    const id = ++counter.current;
    setItems((prev) => [...prev, { id, message, tone }]);
    setTimeout(() => {
      setItems((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
      setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 240);
    }, 2400);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {items.map((t) => (
          <div
            key={t.id}
            className={`toast glass-strong ${t.leaving ? 'leaving' : ''}`}
            style={{ borderColor: `var(--${t.tone === 'accent' ? 'accent-border' : t.tone + '-border'})` }}
          >
            {t.tone === 'danger' ? (
              <XIcon width={15} height={15} color="var(--danger)" />
            ) : (
              <CheckIcon width={15} height={15} color={t.tone === 'success' ? 'var(--success)' : 'var(--accent-strong)'} />
            )}
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
