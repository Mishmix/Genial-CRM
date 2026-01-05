import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { isTelegramWebApp } from '../telegram/webapp';
import BackgroundEffects from './BackgroundEffects';
import { useGlobalShortcuts } from '../hooks/useKeyboardShortcuts';

const navItems = [
  { path: '/', label: 'Обращения', icon: '💬', desc: 'Входящие запросы', shortcut: '⌘1' },
  { path: '/clients', label: 'Клиенты', icon: '👥', desc: 'База контактов', shortcut: '⌘2' },
  { path: '/orders', label: 'Заказы', icon: '📦', desc: 'Доска заказов', shortcut: '⌘3' },
  { path: '/templates', label: 'Шаблоны', icon: '📝', desc: 'Быстрые ответы', shortcut: '⌘4' },
  { path: '/ai', label: 'AI', icon: '🤖', desc: 'Классификация' },
  { path: '/export', label: 'Экспорт', icon: '📤', desc: 'Выгрузка данных' },
  { path: '/settings', label: 'Настройки', icon: '⚙️', desc: 'Параметры', shortcut: '⌘5' },
];

export default function Layout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isTelegram = isTelegramWebApp();
  
  // Enable global keyboard shortcuts
  useGlobalShortcuts();

  return (
    <div className="min-h-screen bg-mesh relative">
      <BackgroundEffects />
      
      {/* Sidebar */}
      <aside 
        className="fixed left-0 top-0 bottom-0 w-72 glass-strong border-r border-[var(--border)] z-40 flex flex-col"
        style={{
          background: 'linear-gradient(180deg, rgba(12, 12, 22, 0.98) 0%, rgba(8, 8, 16, 0.99) 100%)',
        }}
      >
        {/* Logo */}
        <div className="p-6 border-b border-[var(--border)]">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-2xl shadow-lg shadow-purple-500/30">
                🤖
              </div>
              <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-[var(--bg-primary)]" />
            </div>
            <div>
              <h1 className="font-bold text-xl gradient-text">CRM Bot</h1>
              <p className="text-xs text-[var(--text-muted)]">Business Manager</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto">
          <p className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4 px-3">
            Навигация
          </p>
          <div className="space-y-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || 
                (item.path !== '/' && location.pathname.startsWith(item.path));
              
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`nav-item flex items-center gap-4 px-4 py-3.5 rounded-xl transition-colors relative ${
                    isActive
                      ? 'bg-[var(--accent)] text-white'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'
                  }`}
                >
                  {/* Active indicator */}
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-white rounded-r-full" />
                  )}
                  
                  <span className="text-xl">{item.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold">{item.label}</div>
                    <div className={`text-xs truncate ${isActive ? 'text-white/70' : 'text-[var(--text-muted)]'}`}>
                      {item.desc}
                    </div>
                  </div>
                  {item.shortcut && (
                    <span className={`text-xs px-1.5 py-0.5 rounded ${isActive ? 'bg-white/20' : 'bg-[var(--bg-secondary)]'}`}>
                      {item.shortcut}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </div>
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-[var(--border)]">
          {!isTelegram && (
            <button
              type="button"
              onClick={() => { logout(); navigate('/login'); }}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[var(--text-secondary)] hover:bg-red-500/10 hover:text-red-400 transition-colors border border-transparent hover:border-red-500/20"
            >
              <span>🚪</span>
              <span className="font-medium">Выйти</span>
            </button>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="ml-72 min-h-screen relative z-10">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
