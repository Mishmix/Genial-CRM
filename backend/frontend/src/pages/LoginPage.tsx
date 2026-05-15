import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { isTelegramWebApp } from '../telegram/webapp';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 100);
    return () => clearTimeout(timer);
  }, []);

  if (isTelegramWebApp()) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-[#0a0a0f]">
        <div className="text-center animate-fade">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center text-4xl shadow-lg shadow-violet-500/30">
            🤖
          </div>
          <h1 className="text-2xl font-semibold mb-2 text-white">Genial CRM</h1>
          <p className="text-gray-400 mb-6">Подключение...</p>
          <div className="flex justify-center gap-2">
            {[0, 1, 2].map(i => (
              <div 
                key={i} 
                className="w-2 h-2 rounded-full bg-violet-500" 
                style={{ 
                  animation: 'pulse 1.2s ease-in-out infinite', 
                  animationDelay: `${i * 0.15}s` 
                }} 
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try { 
      await login(password, rememberMe); 
      navigate('/'); 
    }
    catch (err) { 
      setError(err instanceof Error ? err.message : 'Ошибка входа'); 
    }
    finally { 
      setLoading(false); 
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-[#0a0a0f] relative overflow-hidden">
      {/* Subtle background gradient */}
      <div 
        className="absolute inset-0 opacity-40"
        style={{
          background: 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(124, 58, 237, 0.15), transparent)'
        }}
      />
      
      <div className={`w-full max-w-sm relative z-10 transition-all duration-500 ${ready ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center text-3xl shadow-lg shadow-violet-500/20">
            🤖
          </div>
          <h1 className="text-xl font-semibold text-white mb-1">Genial CRM</h1>
          <p className="text-gray-500 text-sm">Панель управления</p>
        </div>

        {/* Login form */}
        <div className="bg-[#12121a] border border-gray-800/50 rounded-2xl p-6 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-400 mb-2">
                Пароль
              </label>
              <input 
                type="password" 
                id="password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)} 
                className="w-full h-11 px-4 bg-[#1a1a24] border border-gray-700/50 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all"
                placeholder="••••••••" 
                required 
                autoFocus 
              />
            </div>

            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input 
                type="checkbox" 
                checked={rememberMe} 
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-[#1a1a24] text-violet-600 focus:ring-violet-500/20 focus:ring-offset-0 cursor-pointer"
              />
              <span className="text-sm text-gray-400">Запомнить меня</span>
            </label>

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button 
              type="submit" 
              disabled={loading || !password} 
              className="w-full h-11 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-all duration-200 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Вход...</span>
                </>
              ) : (
                <span>Войти</span>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">
          Genial CRM • Telegram Business
        </p>
      </div>
    </div>
  );
}
