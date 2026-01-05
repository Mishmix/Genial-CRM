import { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

interface ShortcutConfig {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
  description: string;
}

export function useKeyboardShortcuts(shortcuts: ShortcutConfig[]) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in inputs
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
      // Allow Escape to blur inputs
      if (e.key === 'Escape') {
        (e.target as HTMLElement).blur();
      }
      return;
    }

    for (const shortcut of shortcuts) {
      const ctrlMatch = shortcut.ctrl ? (e.ctrlKey || e.metaKey) : !(e.ctrlKey || e.metaKey);
      const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey;
      const altMatch = shortcut.alt ? e.altKey : !e.altKey;
      
      if (e.key.toLowerCase() === shortcut.key.toLowerCase() && ctrlMatch && shiftMatch && altMatch) {
        e.preventDefault();
        shortcut.action();
        return;
      }
    }
  }, [shortcuts]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

// Global navigation shortcuts
export function useGlobalShortcuts() {
  const navigate = useNavigate();

  useKeyboardShortcuts([
    { key: '1', ctrl: true, action: () => navigate('/'), description: 'Обращения' },
    { key: '2', ctrl: true, action: () => navigate('/clients'), description: 'Клиенты' },
    { key: '3', ctrl: true, action: () => navigate('/templates'), description: 'Шаблоны' },
    { key: '4', ctrl: true, action: () => navigate('/ai'), description: 'AI настройки' },
    { key: '5', ctrl: true, action: () => navigate('/settings'), description: 'Настройки' },
  ]);
}

// Shortcut hints component data
export const SHORTCUTS = [
  { keys: ['Ctrl', '1'], description: 'Обращения' },
  { keys: ['Ctrl', '2'], description: 'Клиенты' },
  { keys: ['Ctrl', '3'], description: 'Шаблоны' },
  { keys: ['Ctrl', '4'], description: 'AI' },
  { keys: ['Ctrl', '5'], description: 'Настройки' },
  { keys: ['Esc'], description: 'Закрыть окно' },
];
