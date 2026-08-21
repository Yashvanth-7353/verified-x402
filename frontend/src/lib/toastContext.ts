import { createContext } from 'react';

export interface ToastItem {
  id: number;
  message: string;
  tone: 'success' | 'danger' | 'accent';
  leaving?: boolean;
}

export interface ToastApi {
  show: (message: string, tone?: ToastItem['tone']) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
