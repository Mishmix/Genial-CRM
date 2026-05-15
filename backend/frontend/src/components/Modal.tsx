import { useEffect, useState, ReactNode, useCallback } from 'react';
import { createPortal } from 'react-dom';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}

export default function Modal({ isOpen, onClose, children, className = '', contentClassName = '' }: ModalProps) {
  const [isClosing, setIsClosing] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setShouldRender(true);
      setIsClosing(false);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const handleClose = useCallback(() => {
    setIsClosing(true);
    setTimeout(() => {
      setShouldRender(false);
      setIsClosing(false);
      onClose();
    }, 150);
  }, [onClose]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isClosing) handleClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, isClosing, handleClose]);

  useEffect(() => {
    if (!isOpen || isClosing) return;
    
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('modal-overlay')) {
        handleClose();
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, isClosing, handleClose]);

  // Handle external close (when isOpen becomes false)
  useEffect(() => {
    if (!isOpen && shouldRender && !isClosing) {
      handleClose();
    }
  }, [isOpen, shouldRender, isClosing, handleClose]);

  if (!shouldRender) return null;

  return createPortal(
    <div 
      className={`modal-overlay ${isClosing ? 'closing' : ''} ${className}`} 
      style={{ pointerEvents: 'auto' }}
    >
      <div 
        className={`modal-content ${contentClassName}`} 
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}
