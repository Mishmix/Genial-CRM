import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  onClose: () => void;
  icon?: string;
}

const icons: Record<ToastType, string> = {
  success: '✅',
  error: '❌',
  info: '💡',
};

export default function Toast({ message, type = 'info', duration = 3000, onClose, icon }: ToastProps) {
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true);
      setTimeout(onClose, 200);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  return createPortal(
    <div className={`toast toast-${type} ${isExiting ? 'toast-exit' : ''}`}>
      <span className="text-xl">{icon || icons[type]}</span>
      <span>{message}</span>
    </div>,
    document.body
  );
}

// Toast manager hook
interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  icon?: string;
}

let toastId = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = (message: string, type: ToastType = 'info', icon?: string) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, message, type, icon }]);
  };

  const removeToast = (id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const ToastContainer = () => (
    <>
      {toasts.map(toast => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          icon={toast.icon}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </>
  );

  return {
    showToast,
    success: (msg: string, icon?: string) => showToast(msg, 'success', icon),
    error: (msg: string, icon?: string) => showToast(msg, 'error', icon),
    info: (msg: string, icon?: string) => showToast(msg, 'info', icon),
    ToastContainer,
  };
}
