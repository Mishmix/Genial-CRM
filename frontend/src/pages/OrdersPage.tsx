import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PageWrapper from '../components/PageWrapper';
import Avatar from '../components/Avatar';
import { useToast } from '../contexts/ToastContext';
import { API_BASE } from '../api';

interface OrderClient {
  id: number;
  first_name: string;
  last_name: string | null;
  username: string | null;
  avatar_local_path: string | null;
}

interface BoardOrder {
  id: number;
  client_id: number;
  service_type: string;
  quantity: number;
  amount: number | null;
  deadline_date: string | null;
  status: string;
  notes: string | null;
  source: 'manual' | 'ai';
  ai_confidence: number | null;
  created_at: string;
  client: OrderClient | null;
}

interface OrdersBoard {
  overdue: BoardOrder[];
  today: BoardOrder[];
  later: BoardOrder[];
  completed: BoardOrder[];
}

const SERVICE_LABELS: Record<string, string> = {
  thumbnail: '🖼️ Превью',
  banner: '🎨 Баннер',
  logo: '⭐ Лого',
  channel_design: '📺 Оформление',
  creative: '✨ Креатив',
  other: '📦 Другое',
};

export default function OrdersPage() {
  const [board, setBoard] = useState<OrdersBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({ completed: true });
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    loadBoard();
    // Refresh every 30 seconds
    const interval = setInterval(loadBoard, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadBoard = async () => {
    try {
      const response = await fetch(`${API_BASE}/orders/board`, { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setBoard(data);
      }
    } catch (err) {
      console.error('Failed to load orders board:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteOrder = async (orderId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/orders/${orderId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ status: 'completed' })
      });
      toast.success('Заказ выполнен!', '✅');
      loadBoard();
    } catch (err) {
      toast.error('Ошибка');
    }
  };

  const handleDeleteOrder = async (orderId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/orders/${orderId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      toast.success('Заказ удалён');
      loadBoard();
    } catch (err) {
      toast.error('Ошибка');
    }
  };

  const handleSyncTodoist = async () => {
    setSyncing(true);
    try {
      const response = await fetch(`${API_BASE}/todoist/sync`, {
        method: 'POST',
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        if (data.completed_count > 0) {
          toast.success(`Синхронизировано: ${data.completed_count} заказов`, '🔄');
        } else {
          toast.info('Нет новых выполненных задач');
        }
        loadBoard();
      } else {
        const err = await response.json();
        toast.error(err.detail || 'Ошибка синхронизации');
      }
    } catch (err) {
      toast.error('Ошибка синхронизации с Todoist');
    } finally {
      setSyncing(false);
    }
  };

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Без дедлайна';
    const date = new Date(dateStr);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    
    if (date.toDateString() === today.toDateString()) return 'Сегодня';
    if (date.toDateString() === tomorrow.toDateString()) return 'Завтра';
    
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  // Group later orders by date
  const groupByDate = (orders: BoardOrder[]) => {
    const groups: Record<string, BoardOrder[]> = {};
    orders.forEach(order => {
      const key = order.deadline_date ? formatDate(order.deadline_date) : 'Без дедлайна';
      if (!groups[key]) groups[key] = [];
      groups[key].push(order);
    });
    return groups;
  };

  const stats = board ? {
    total: board.overdue.length + board.today.length + board.later.length,
    overdue: board.overdue.length,
    today: board.today.length,
    completed: board.completed?.length || 0,
    ai: [...board.overdue, ...board.today, ...board.later].filter(o => o.source === 'ai').length,
  } : { total: 0, overdue: 0, today: 0, completed: 0, ai: 0 };

  const OrderCard = ({ order }: { order: BoardOrder }) => (
    <div 
      onClick={() => navigate(`/clients/${order.client_id}`)}
      className="flex items-center gap-4 p-4 rounded-xl bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] cursor-pointer transition-colors group relative"
    >
      {/* Avatar */}
      <Avatar name={order.client?.first_name || '?'} size="md" />
      
      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-[var(--text-primary)]">
            {SERVICE_LABELS[order.service_type] || order.service_type}
            {order.quantity > 1 && ` ×${order.quantity}`}
          </span>
        </div>
        <div className="text-sm text-[var(--text-muted)]">
          {order.client ? (
            order.client.username ? `@${order.client.username}` : order.client.first_name
          ) : 'Неизвестный клиент'}
        </div>
      </div>
      
      {/* Right side */}
      <div className="flex items-center gap-3">
        {order.amount && (
          <span className="text-emerald-400 font-semibold">${order.amount}</span>
        )}
        
        {/* Source badge */}
        <span className={`text-xs px-2 py-1 rounded-full ${
          order.source === 'ai' 
            ? 'bg-purple-500/20 text-purple-400' 
            : 'bg-blue-500/20 text-blue-400'
        }`}>
          {order.source === 'ai' ? '🤖' : '👤'}
        </span>
        
        {/* Action buttons - visible on hover */}
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => handleCompleteOrder(order.id, e)}
            className="p-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 transition-colors"
            title="Выполнено"
          >
            ✓
          </button>
          <button
            onClick={(e) => handleDeleteOrder(order.id, e)}
            className="p-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 transition-colors"
            title="Удалить"
          >
            ✕
          </button>
        </div>
      </div>
      
      {/* AI confidence bar */}
      {order.source === 'ai' && order.ai_confidence && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-700/50 rounded-b-xl overflow-hidden">
          <div 
            className="h-full bg-purple-500/50"
            style={{ width: `${order.ai_confidence * 100}%` }}
          />
        </div>
      )}
    </div>
  );

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-2xl shadow-lg shadow-emerald-500/30">📦</div>
              <div>
                <h1 className="text-3xl font-bold"><span className="gradient-text">Заказы</span></h1>
                <p className="text-[var(--text-secondary)]">Доска заказов Today / Not Today</p>
              </div>
            </div>
            <button
              onClick={handleSyncTodoist}
              disabled={syncing}
              className="btn btn-secondary"
              title="Синхронизировать с Todoist"
            >
              {syncing ? '🔄 Синхронизация...' : '🔄 Sync Todoist'}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="card p-4 text-center">
            <div className="text-3xl font-bold text-white">{stats.total}</div>
            <div className="text-sm text-[var(--text-muted)]">В работе</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-3xl font-bold text-red-400">{stats.overdue}</div>
            <div className="text-sm text-[var(--text-muted)]">Просрочено</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-3xl font-bold text-amber-400">{stats.today}</div>
            <div className="text-sm text-[var(--text-muted)]">Сегодня</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-3xl font-bold text-emerald-400">{stats.completed}</div>
            <div className="text-sm text-[var(--text-muted)]">Выполнено</div>
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-6">
          {/* Overdue */}
          {board && board.overdue.length > 0 && (
            <div className="card p-5">
              <div 
                className="flex items-center justify-between cursor-pointer mb-4"
                onClick={() => toggleSection('overdue')}
              >
                <h2 className="text-lg font-semibold text-red-400 flex items-center gap-2">
                  ⚠️ ПРОСРОЧЕНО
                  <span className="text-sm bg-red-500/20 px-2 py-0.5 rounded-full">{board.overdue.length}</span>
                </h2>
                <span className="text-[var(--text-muted)]">{collapsedSections.overdue ? '▼' : '▲'}</span>
              </div>
              {!collapsedSections.overdue && (
                <div className="space-y-3">
                  {board.overdue.map(order => (
                    <OrderCard key={order.id} order={order} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Today */}
          <div className="card p-5">
            <div 
              className="flex items-center justify-between cursor-pointer mb-4"
              onClick={() => toggleSection('today')}
            >
              <h2 className="text-lg font-semibold text-amber-400 flex items-center gap-2">
                📅 СЕГОДНЯ
                <span className="text-sm bg-amber-500/20 px-2 py-0.5 rounded-full">{board?.today.length || 0}</span>
              </h2>
              <span className="text-[var(--text-muted)]">{collapsedSections.today ? '▼' : '▲'}</span>
            </div>
            {!collapsedSections.today && (
              board?.today.length ? (
                <div className="space-y-3">
                  {board.today.map(order => (
                    <OrderCard key={order.id} order={order} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-[var(--text-muted)]">
                  Нет заказов на сегодня 🎉
                </div>
              )
            )}
          </div>

          {/* Later */}
          <div className="card p-5">
            <div 
              className="flex items-center justify-between cursor-pointer mb-4"
              onClick={() => toggleSection('later')}
            >
              <h2 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                📆 ПОЗЖЕ
                <span className="text-sm bg-[var(--bg-hover)] px-2 py-0.5 rounded-full">{board?.later.length || 0}</span>
              </h2>
              <span className="text-[var(--text-muted)]">{collapsedSections.later ? '▼' : '▲'}</span>
            </div>
            {!collapsedSections.later && board?.later.length ? (
              <div className="space-y-4">
                {Object.entries(groupByDate(board.later)).map(([date, orders]) => (
                  <div key={date}>
                    <div className="text-sm font-medium text-[var(--text-muted)] mb-2 px-1">{date}</div>
                    <div className="space-y-3">
                      {orders.map(order => (
                        <OrderCard key={order.id} order={order} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : !collapsedSections.later && (
              <div className="text-center py-8 text-[var(--text-muted)]">
                Нет запланированных заказов
              </div>
            )}
          </div>

          {/* Completed */}
          {board?.completed && board.completed.length > 0 && (
            <div className="card p-5">
              <div 
                className="flex items-center justify-between cursor-pointer mb-4"
                onClick={() => toggleSection('completed')}
              >
                <h2 className="text-lg font-semibold text-emerald-400 flex items-center gap-2">
                  ✅ ВЫПОЛНЕНО
                  <span className="text-sm bg-emerald-500/20 px-2 py-0.5 rounded-full">{board.completed.length}</span>
                </h2>
                <span className="text-[var(--text-muted)]">{collapsedSections.completed ? '▼' : '▲'}</span>
              </div>
              {!collapsedSections.completed && (
                <div className="space-y-3">
                  {board.completed.map(order => (
                    <div 
                      key={order.id}
                      onClick={() => navigate(`/clients/${order.client_id}`)}
                      className="flex items-center gap-4 p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 cursor-pointer transition-colors hover:bg-emerald-500/10"
                    >
                      {/* Avatar */}
                      <Avatar name={order.client?.first_name || '?'} size="md" />
                      
                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-emerald-400/80 line-through">
                            {SERVICE_LABELS[order.service_type] || order.service_type}
                            {order.quantity > 1 && ` ×${order.quantity}`}
                          </span>
                        </div>
                        <div className="text-sm text-[var(--text-muted)]">
                          {order.client ? (
                            order.client.username ? `@${order.client.username}` : order.client.first_name
                          ) : 'Неизвестный клиент'}
                        </div>
                      </div>
                      
                      {/* Amount */}
                      {order.amount && (
                        <span className="text-emerald-400/60 font-semibold">${order.amount}</span>
                      )}}
                      
                      {/* Completed badge */}
                      <span className="text-xs px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400">
                        ✓ Готово
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-6 flex items-center justify-center gap-6 text-sm text-[var(--text-muted)]">
          <span className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400">🤖</span>
            AI детекция
          </span>
          <span className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">👤</span>
            Вручную
          </span>
        </div>
      </div>
    </PageWrapper>
  );
}
