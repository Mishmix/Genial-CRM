import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getConversations, deleteConversation, Conversation } from '../api';
import PageWrapper from '../components/PageWrapper';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../contexts/ToastContext';
import { formatRelativeTime } from '../utils/date';

// Status options for filter
const STATUS_OPTIONS = [
  { value: '', label: 'Все', icon: '📊' },
  { value: 'new', label: 'Новые', icon: '✨' },
  { value: 'ordered', label: 'Заказ', icon: '✅' },
  { value: 'rejected', label: 'Отказ', icon: '❌' },
];

// Period options for filter
const PERIOD_OPTIONS = [
  { value: '', label: 'Все время' },
  { value: '24h', label: '24ч' },
  { value: '48h', label: '48ч' },
  { value: '7d', label: '7д' },
  { value: '30d', label: '30д' },
];

// Category options
const CATEGORY_OPTIONS = [
  { value: '', label: 'Все типы', icon: '📁' },
  { value: 'thumbnail', label: 'Превью', icon: '🖼️' },
  { value: 'banner', label: 'Баннер', icon: '🎨' },
  { value: 'logo', label: 'Логотип', icon: '⭐' },
  { value: 'channel_design', label: 'Оформление', icon: '📺' },
  { value: 'other', label: 'Другое', icon: '📦' },
];

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [periodFilter, setPeriodFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [unreadFilter, setUnreadFilter] = useState(false);
  const [total, setTotal] = useState(0);
  const [deleting, setDeleting] = useState<number | null>(null);
  const navigate = useNavigate();
  const toast = useToast();
  
  const conversationsRef = useRef<Conversation[]>([]);
  conversationsRef.current = conversations;

  // Real-time updates via WebSocket
  useWebSocket('new_message', (data: any) => {
    console.log('[ConversationsPage] Received new_message:', data);
    
    if (data.conversation_id) {
      const currentConversations = conversationsRef.current;
      const idx = currentConversations.findIndex(c => c.id === data.conversation_id);
      
      if (idx >= 0) {
        // Update existing conversation and move to top
        const updated = [...currentConversations];
        updated[idx] = {
          ...updated[idx],
          unread_count: (updated[idx].unread_count || 0) + 1,
          updated_at: new Date().toISOString(),
        };
        const [conv] = updated.splice(idx, 1);
        setConversations([conv, ...updated]);
      } else {
        // New conversation - reload list
        loadConversations();
      }
    }
  });

  // Handle conversation read (when owner replies in Telegram)
  useWebSocket('conversation_read', (data: any) => {
    console.log('[ConversationsPage] Received conversation_read:', data);
    
    if (data.conversation_id) {
      setConversations(prev => prev.map(c => 
        c.id === data.conversation_id 
          ? { ...c, unread_count: 0 }
          : c
      ));
    }
  });

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getConversations({
        status: statusFilter || undefined,
        period: periodFilter || undefined,
        category: categoryFilter || undefined,
        has_unread: unreadFilter || undefined,
      });
      setConversations(result.items);
      setTotal(result.total);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, periodFilter, categoryFilter, unreadFilter]);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—';
    return formatRelativeTime(dateStr);
  };

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  const getStatusBadge = (status: string) => {
    const opt = STATUS_OPTIONS.find(s => s.value === status);
    return opt ? `${opt.icon} ${opt.label}` : status;
  };

  const handleDelete = async (e: React.MouseEvent, convId: number) => {
    e.stopPropagation(); // Prevent navigation
    setDeleting(convId);
    try {
      await deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      setTotal(prev => prev - 1);
      toast.success('Обращение удалено', '🗑️');
    } catch (err) {
      toast.error('Ошибка удаления');
    } finally {
      setDeleting(null);
    }
  };

  const stats = {
    total,
    new: conversations.filter(c => c.status === 'new').length,
    unread: conversations.filter(c => (c.unread_count || 0) > 0).length,
    ordered: conversations.reduce((sum, c) => sum + (c.orders_count || 0), 0),
  };

  const statCards = [
    { label: 'Всего обращений', value: stats.total, icon: '💬', gradient: 'from-violet-500/25 via-purple-500/20 to-fuchsia-500/15', iconBg: 'from-violet-500 to-purple-600' },
    { label: 'Новые', value: stats.new, icon: '✨', gradient: 'from-blue-500/25 via-cyan-500/20 to-teal-500/15', iconBg: 'from-blue-500 to-cyan-500' },
    { label: 'Непрочитанные', value: stats.unread, icon: '📩', gradient: 'from-orange-500/25 via-amber-500/20 to-yellow-500/15', iconBg: 'from-orange-500 to-amber-500' },
    { label: 'Заказы', value: stats.ordered, icon: '✅', gradient: 'from-emerald-500/25 via-green-500/20 to-teal-500/15', iconBg: 'from-emerald-500 to-green-500' },
  ];

  // Filter conversations by search
  const filteredConversations = search.trim()
    ? conversations.filter(c => {
        const client = c.client;
        if (!client) return false;
        const searchLower = search.toLowerCase();
        return (
          client.first_name?.toLowerCase().includes(searchLower) ||
          client.last_name?.toLowerCase().includes(searchLower) ||
          client.username?.toLowerCase().includes(searchLower)
        );
      })
    : conversations;

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-2xl shadow-lg shadow-violet-500/30">💬</div>
            <div>
              <h1 className="text-3xl font-bold"><span className="gradient-text">Обращения</span></h1>
              <p className="text-[var(--text-secondary)]">Управление входящими запросами</p>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-5 mb-8">
          {statCards.map((stat) => (
            <div key={stat.label} className="card stat-card p-5 stagger-item">
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.gradient} rounded-[20px] opacity-60`} />
              <div className="flex items-center justify-between relative z-10">
                <div>
                  <p className="text-[var(--text-muted)] text-sm font-medium mb-1">{stat.label}</p>
                  <p className="text-4xl font-bold text-white">{stat.value}</p>
                </div>
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${stat.iconBg} flex items-center justify-center text-2xl shadow-lg`}>
                  {stat.icon}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Search & Filters */}
        <div className="card p-5 mb-6">
          {/* Search */}
          <div className="relative mb-4">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)] text-lg pointer-events-none">🔍</span>
            <input 
              type="text" 
              placeholder="Поиск по имени или username..." 
              value={search} 
              onChange={(e) => setSearch(e.target.value)} 
              className="input text-base h-12 w-full" 
              style={{ paddingLeft: '48px' }}
            />
          </div>
          
          {/* Period filters */}
          <div className="flex flex-wrap gap-2 mb-4">
            {PERIOD_OPTIONS.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setPeriodFilter(opt.value)}
                className={`btn btn-sm ${periodFilter === opt.value ? 'btn-primary' : 'btn-secondary'}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          
          {/* Status & Category filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <select 
              value={statusFilter} 
              onChange={(e) => setStatusFilter(e.target.value)} 
              className="input" 
              style={{ width: '150px' }}
            >
              {STATUS_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>
              ))}
            </select>
            
            <select 
              value={categoryFilter} 
              onChange={(e) => setCategoryFilter(e.target.value)} 
              className="input" 
              style={{ width: '170px' }}
            >
              {CATEGORY_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>
              ))}
            </select>
            
            <button 
              type="button" 
              onClick={() => setUnreadFilter(!unreadFilter)} 
              className={`btn px-4 ${unreadFilter ? 'btn-primary' : 'btn-secondary'} relative`}
            >
              📩 Непрочитанные
              {unreadFilter && <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-[var(--bg-card)]" />}
            </button>
          </div>
        </div>

        {/* Conversations list */}
        {loading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="card p-5">
                <div className="flex items-center gap-4">
                  <div className="skeleton w-14 h-14 rounded-2xl" />
                  <div className="flex-1"><div className="skeleton h-5 w-44 mb-2" /><div className="skeleton h-4 w-32" /></div>
                  <div className="skeleton h-8 w-28 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="card card-gradient">
            <div className="empty-state py-20">
              <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-violet-500/30 to-purple-500/20 flex items-center justify-center text-5xl mb-6 mx-auto">
                {search ? '🔍' : '💬'}
              </div>
              <div className="empty-state-title text-2xl mb-2 text-white">
                {search ? 'Ничего не найдено' : 'Нет обращений'}
              </div>
              <div className="empty-state-text text-base text-[var(--text-secondary)]">
                {search ? 'Попробуйте изменить поисковый запрос' : 'Обращения появятся когда клиенты напишут вам'}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredConversations.map((conv) => {
              const client = conv.client;
              if (!client) return null;
              
              return (
                <div 
                  key={conv.id} 
                  onClick={() => navigate(`/conversations/${conv.id}`)} 
                  className="card card-hover card-interactive p-5 cursor-pointer stagger-item group"
                >
                  <div className="flex items-center gap-5">
                    {/* Status indicator */}
                    <div className={`w-3 h-3 rounded-full flex-shrink-0 ${
                      conv.status === 'new' ? 'bg-violet-500 animate-pulse' :
                      conv.status === 'ordered' ? 'bg-emerald-500' :
                      conv.status === 'rejected' ? 'bg-red-500' : 'bg-gray-500'
                    }`} />
                    
                    {/* Avatar */}
                    {client.avatar_local_path ? (
                      <img 
                        src={`http://localhost:8000${client.avatar_local_path}`}
                        alt={client.first_name}
                        className="w-12 h-12 rounded-2xl object-cover"
                      />
                    ) : (
                      <div className="avatar avatar-md">
                        {getInitials(client.first_name)}
                      </div>
                    )}
                    
                    {/* Client info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1.5">
                        <span className="font-semibold text-lg truncate text-white">
                          {client.first_name} {client.last_name || ''}
                        </span>
                        {(conv.unread_count || 0) > 0 && (
                          <span className="unread-badge">{conv.unread_count}</span>
                        )}
                        {client.status === 'repeat' && (
                          <span className="tag bg-blue-500/20 text-blue-400 border border-blue-500/40">🔄 Повторный</span>
                        )}
                        {client.status === 'difficult' && (
                          <span className="tag bg-amber-500/20 text-amber-400 border border-amber-500/40">⚠️ Сложный</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-sm">
                        <span className="text-[var(--text-muted)]">
                          {client.username ? `@${client.username}` : `ID: ${client.telegram_user_id}`}
                        </span>
                        {conv.category && (
                          <span className="tag bg-[var(--bg-hover)] text-[var(--text-secondary)] border border-[var(--border)]">
                            {CATEGORY_OPTIONS.find(c => c.value === conv.category)?.icon} {conv.category}
                          </span>
                        )}
                        {client.tags && client.tags.length > 0 && (
                          <div className="flex gap-1.5">
                            {client.tags.slice(0, 2).map(tag => (
                              <span 
                                key={tag.id} 
                                className="tag" 
                                style={{ backgroundColor: tag.color + '40', color: tag.color, border: `1px solid ${tag.color}60` }}
                              >
                                {tag.name}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {/* Sticky note preview */}
                      {client.sticky_note && (
                        <div className="mt-2 text-sm text-amber-400/80 truncate">
                          📌 {client.sticky_note}
                        </div>
                      )}
                    </div>
                    
                    {/* Right side info */}
                    <div className="flex items-center gap-5">
                      <span className={`badge badge-${conv.status}`}>
                        {getStatusBadge(conv.status)}
                      </span>
                      {(conv.total_amount || 0) > 0 && (
                        <span className="text-emerald-400 font-semibold">
                          ${conv.total_amount}
                        </span>
                      )}
                      <span className="text-sm text-[var(--text-muted)] w-16 text-right font-medium tabular-nums">
                        {formatDate(conv.updated_at || conv.created_at)}
                      </span>
                      <button
                        onClick={(e) => handleDelete(e, conv.id)}
                        disabled={deleting === conv.id}
                        className="p-2 rounded-xl hover:bg-red-500/20 text-[var(--text-muted)] hover:text-red-400 transition-all opacity-0 group-hover:opacity-100"
                        title="Удалить обращение"
                      >
                        {deleting === conv.id ? (
                          <div className="w-5 h-5 border-2 border-red-400/30 border-t-red-400 rounded-full animate-spin" />
                        ) : (
                          <span className="text-lg">✕</span>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
