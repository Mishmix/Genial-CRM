import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { createPortal } from 'react-dom';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
  icon?: string;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, icon?: string) => void;
  success: (message: string, icon?: string) => void;
  error: (message: string, icon?: string) => void;
  info: (message: string, icon?: string) => void;
  warning: (message: string, icon?: string) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

let toastId = 0;

const icons: Record<ToastType, string> = {
  success: '✅',
  error: '❌',
  info: '💡',
  warning: '⚠️',
};

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: () => void }) {
  const [isExiting, setIsExiting] = useState(false);

  useState(() => {
    const timer = setTimeout(() => {
      setIsExiting(true);
      setTimeout(onRemove, 200);
    }, 3000);
    return () => clearTimeout(timer);
  });

  return (
    <div 
      className={`toast toast-${toast.type} ${isExiting ? 'toast-exit' : ''}`}
      style={{ position: 'relative', marginBottom: '10px' }}
    >
      <span className="text-xl">{toast.icon || icons[toast.type]}</span>
      <span>{toast.message}</span>
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = 'info', icon?: string) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, message, type, icon }]);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3200);
  }, []);

  const success = useCallback((msg: string, icon?: string) => showToast(msg, 'success', icon), [showToast]);
  const error = useCallback((msg: string, icon?: string) => showToast(msg, 'error', icon), [showToast]);
  const info = useCallback((msg: string, icon?: string) => showToast(msg, 'info', icon), [showToast]);
  const warning = useCallback((msg: string, icon?: string) => showToast(msg, 'warning', icon), [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, success, error, info, warning }}>
      {children}
      {toasts.length > 0 && createPortal(
        <div className="toast-container">
          {toasts.map(toast => (
            <ToastItem 
              key={toast.id} 
              toast={toast} 
              onRemove={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
            />
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
