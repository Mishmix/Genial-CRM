import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { isTelegramWebApp } from '../telegram/webapp';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [ready, setReady] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 100);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
      }
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  if (isTelegramWebApp()) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-mesh">
        <div className="text-center animate-fade">
          <div className="w-28 h-28 mx-auto mb-8 rounded-3xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-6xl shadow-2xl shadow-violet-500/50 animate-float">🤖</div>
          <h1 className="text-4xl font-bold mb-3 gradient-text">CRM Bot</h1>
          <p className="text-[var(--text-secondary)] mb-8 text-lg">Подключение к Telegram...</p>
          <div className="flex justify-center gap-3">
            {[0, 1, 2].map(i => (
              <div key={i} className="w-3 h-3 rounded-full bg-gradient-to-r from-violet-500 to-purple-500" style={{ animation: 'pulse 1.5s ease-in-out infinite', animationDelay: `${i * 0.2}s` }} />
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
    try { await login(password); navigate('/'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Login failed'); }
    finally { setLoading(false); }
  };

  return (
    <div ref={containerRef} className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden bg-mesh">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Glow orbs */}
        <div className="absolute w-[700px] h-[700px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(124, 58, 237, 0.35) 0%, transparent 70%)', top: '-250px', left: '-250px', filter: 'blur(80px)', animation: 'float 8s ease-in-out infinite' }} />
        <div className="absolute w-[600px] h-[600px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(168, 85, 247, 0.3) 0%, transparent 70%)', bottom: '-200px', right: '-200px', filter: 'blur(80px)', animation: 'float 10s ease-in-out infinite reverse' }} />
        <div className="absolute w-[500px] h-[500px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(34, 211, 238, 0.2) 0%, transparent 70%)', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', filter: 'blur(80px)', animation: 'pulse 6s ease-in-out infinite' }} />

        {/* Floating particles */}
        {Array.from({ length: 30 }).map((_, i) => (
          <div key={i} className="absolute rounded-full" style={{
            width: `${2 + Math.random() * 4}px`,
            height: `${2 + Math.random() * 4}px`,
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            background: ['var(--accent)', 'var(--accent-secondary)', 'var(--accent-tertiary)', '#ec4899'][i % 4],
            opacity: 0.2 + Math.random() * 0.4,
            animation: `float ${8 + Math.random() * 8}s ease-in-out infinite`,
            animationDelay: `${Math.random() * 5}s`,
            boxShadow: `0 0 ${6 + Math.random() * 6}px currentColor`,
          }} />
        ))}

        {/* Grid */}
        <div className="absolute inset-0 bg-grid opacity-40" style={{ maskImage: 'radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 100%)', WebkitMaskImage: 'radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 100%)' }} />
        
        {/* Top gradient line */}
        <div className="absolute top-0 left-0 right-0 h-px" style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(124, 58, 237, 0.5) 20%, rgba(168, 85, 247, 0.5) 50%, rgba(34, 211, 238, 0.5) 80%, transparent 100%)' }} />
      </div>

      {/* Spotlight following cursor */}
      <div className="absolute pointer-events-none transition-all duration-150 ease-out" style={{ width: '600px', height: '600px', left: mousePos.x, top: mousePos.y, transform: 'translate(-50%, -50%)', background: 'radial-gradient(circle, rgba(124, 58, 237, 0.12) 0%, rgba(168, 85, 247, 0.05) 40%, transparent 70%)' }} />

      <div className={`w-full max-w-md relative z-10 transition-all duration-700 ${ready ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="relative inline-block">
            <div className="w-28 h-28 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-6xl shadow-2xl animate-float" style={{ boxShadow: '0 20px 60px -10px rgba(124, 58, 237, 0.5), 0 0 80px -20px rgba(168, 85, 247, 0.4)' }}>
              🤖
            </div>
            <div className="absolute -inset-4 rounded-[32px] animate-glow opacity-50" style={{ background: 'transparent', boxShadow: '0 0 60px var(--accent-glow)' }} />
          </div>
          <h1 className="text-4xl font-bold mb-3"><span className="gradient-text">С возвращением</span></h1>
          <p className="text-[var(--text-secondary)] text-lg">Войдите в панель управления CRM</p>
        </div>

        {/* Login card */}
        <div className="card card-glow p-8 relative" style={{ boxShadow: '0 25px 80px -20px rgba(0, 0, 0, 0.5), 0 0 60px -20px var(--accent-glow)' }}>
          <div className="absolute inset-0 rounded-[20px] pointer-events-none" style={{ background: `radial-gradient(circle at ${mousePos.x}px ${mousePos.y}px, rgba(124, 58, 237, 0.08) 0%, transparent 50%)` }} />

          <form onSubmit={handleSubmit} className="space-y-6 relative">
            <div>
              <label htmlFor="password" className="block text-sm font-semibold text-[var(--text-secondary)] mb-3">Пароль</label>
              <div className="relative group">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)] text-xl group-focus-within:text-[var(--accent)] transition-colors">🔐</span>
                <input type="password" id="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input pl-14 h-14 text-base" placeholder="Введите пароль" required autoFocus />
              </div>
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-3 animate-scale">
                <span className="text-xl">⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading || !password} className="btn btn-primary w-full h-14 text-base font-semibold">
              {loading ? (
                <div className="flex items-center gap-3">
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Вход...</span>
                </div>
              ) : (
                <span>Войти <span className="ml-1">→</span></span>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-[var(--border)] text-center">
            <p className="text-sm text-[var(--text-muted)] flex items-center justify-center gap-2">
              <span className="text-base">💡</span> Откройте из Telegram для доступа к Mini App
            </p>
          </div>
        </div>

        <p className="text-center text-sm text-[var(--text-muted)] mt-8 flex items-center justify-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          Защищено шифрованием
        </p>
      </div>
    </div>
  );
}
