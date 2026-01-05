import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { getMe, authTelegram, authPassword, logout as apiLogout } from '../api';
import { getInitData, isTelegramWebApp } from '../telegram/webapp';

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  authType: string | null;
  telegramUserId: number | null;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: (password: string) => Promise<void>;
  loginTelegram: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    authType: null,
    telegramUserId: null,
    error: null,
  });

  // Check auth status on mount
  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      // If in Telegram, try to auth with initData
      if (isTelegramWebApp()) {
        const initData = getInitData();
        if (initData) {
          try {
            await authTelegram(initData);
          } catch (e) {
            // Telegram auth failed, will show error
            setState(s => ({
              ...s,
              isLoading: false,
              error: 'Access denied. You are not an admin.',
            }));
            return;
          }
        }
      }

      // Check if we have a valid session
      const me = await getMe();
      setState({
        isAuthenticated: me.authenticated,
        isLoading: false,
        authType: me.auth_type,
        telegramUserId: me.telegram_user_id || null,
        error: null,
      });
    } catch (e) {
      setState({
        isAuthenticated: false,
        isLoading: false,
        authType: null,
        telegramUserId: null,
        error: null,
      });
    }
  }

  async function login(password: string) {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      await authPassword(password);
      setState({
        isAuthenticated: true,
        isLoading: false,
        authType: 'password',
        telegramUserId: null,
        error: null,
      });
    } catch (e) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: e instanceof Error ? e.message : 'Login failed',
      }));
      throw e;
    }
  }

  async function loginTelegram() {
    const initData = getInitData();
    if (!initData) {
      throw new Error('Not in Telegram');
    }

    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const result = await authTelegram(initData);
      setState({
        isAuthenticated: true,
        isLoading: false,
        authType: 'telegram',
        telegramUserId: result.user_id || null,
        error: null,
      });
    } catch (e) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: e instanceof Error ? e.message : 'Telegram auth failed',
      }));
      throw e;
    }
  }

  async function logout() {
    try {
      await apiLogout();
    } finally {
      setState({
        isAuthenticated: false,
        isLoading: false,
        authType: null,
        telegramUserId: null,
        error: null,
      });
    }
  }

  return (
    <AuthContext.Provider value={{ ...state, login, loginTelegram, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
