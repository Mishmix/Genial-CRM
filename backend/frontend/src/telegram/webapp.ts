/**
 * Telegram Mini App SDK integration
 */

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    auth_date: number;
    hash: string;
  };
  colorScheme: 'light' | 'dark';
  themeParams: {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
  };
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  ready: () => void;
  expand: () => void;
  close: () => void;
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
    setText: (text: string) => void;
    enable: () => void;
    disable: () => void;
  };
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
    selectionChanged: () => void;
  };
}

export function isTelegramWebApp(): boolean {
  return typeof window !== 'undefined' && !!window.Telegram?.WebApp?.initData;
}

export function getTelegramWebApp(): TelegramWebApp | null {
  if (isTelegramWebApp()) {
    return window.Telegram!.WebApp;
  }
  return null;
}

export function getInitData(): string | null {
  const webapp = getTelegramWebApp();
  return webapp?.initData || null;
}

export function getTelegramUser() {
  const webapp = getTelegramWebApp();
  return webapp?.initDataUnsafe?.user || null;
}

export function initTelegramWebApp(): void {
  const webapp = getTelegramWebApp();
  if (webapp) {
    // Tell Telegram the app is ready
    webapp.ready();
    
    // Expand to full height
    webapp.expand();
    
    // Apply theme colors
    applyThemeColors(webapp.themeParams);
    
    console.log('Telegram WebApp initialized');
  }
}

function applyThemeColors(params: TelegramWebApp['themeParams']): void {
  const root = document.documentElement;
  
  if (params.bg_color) {
    root.style.setProperty('--tg-theme-bg-color', params.bg_color);
  }
  if (params.text_color) {
    root.style.setProperty('--tg-theme-text-color', params.text_color);
  }
  if (params.hint_color) {
    root.style.setProperty('--tg-theme-hint-color', params.hint_color);
  }
  if (params.link_color) {
    root.style.setProperty('--tg-theme-link-color', params.link_color);
  }
  if (params.button_color) {
    root.style.setProperty('--tg-theme-button-color', params.button_color);
  }
  if (params.button_text_color) {
    root.style.setProperty('--tg-theme-button-text-color', params.button_text_color);
  }
  if (params.secondary_bg_color) {
    root.style.setProperty('--tg-theme-secondary-bg-color', params.secondary_bg_color);
  }
}

export function hapticFeedback(type: 'success' | 'error' | 'warning' | 'light' | 'medium' | 'heavy'): void {
  const webapp = getTelegramWebApp();
  if (!webapp?.HapticFeedback) return;
  
  if (type === 'success' || type === 'error' || type === 'warning') {
    webapp.HapticFeedback.notificationOccurred(type);
  } else {
    webapp.HapticFeedback.impactOccurred(type);
  }
}
