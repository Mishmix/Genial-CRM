import { Order, Message } from '../api';

interface TimelineItem {
  id: string;
  type: 'order' | 'message' | 'status_change';
  date: string;
  data: Order | Message | { status: string; from?: string };
}

interface TimelineProps {
  orders: Order[];
  messages: Message[];
  className?: string;
}

const SERVICE_LABELS: Record<string, string> = {
  thumbnail: '🎨 Превью',
  banner: '🖼️ Баннер',
  logo: '✨ Лого',
  channel_design: '📺 Дизайн канала',
  other: '📦 Другое',
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: 'В работе', color: 'text-amber-400' },
  completed: { label: 'Выполнен', color: 'text-emerald-400' },
  cancelled: { label: 'Отменён', color: 'text-red-400' },
  refunded: { label: 'Возврат', color: 'text-orange-400' },
};

export default function Timeline({ orders, messages, className = '' }: TimelineProps) {
  // Combine and sort items by date
  const items: TimelineItem[] = [
    ...orders.map(o => ({
      id: `order-${o.id}`,
      type: 'order' as const,
      date: o.created_at,
      data: o,
    })),
    // Only show outgoing messages in timeline (key interactions)
    ...messages.filter(m => m.direction === 'out').slice(-10).map(m => ({
      id: `msg-${m.id}`,
      type: 'message' as const,
      date: m.sent_at,
      data: m,
    })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 86400000) {
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }
    if (diff < 604800000) {
      return date.toLocaleDateString('ru-RU', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  if (items.length === 0) {
    return (
      <div className={`text-center py-8 text-[var(--text-muted)] ${className}`}>
        <div className="text-3xl mb-2">📋</div>
        <div className="text-sm">История пуста</div>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {items.slice(0, 15).map((item, idx) => (
        <div key={item.id} className="flex gap-3 animate-fadeIn" style={{ animationDelay: `${idx * 30}ms` }}>
          {/* Timeline line */}
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-sm ${
              item.type === 'order' 
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                : 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
            }`}>
              {item.type === 'order' ? '📦' : '💬'}
            </div>
            {idx < items.length - 1 && (
              <div className="w-0.5 flex-1 bg-[var(--border)] my-1" />
            )}
          </div>
          
          {/* Content */}
          <div className="flex-1 pb-3">
            {item.type === 'order' && (
              <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">
                    {SERVICE_LABELS[(item.data as Order).service_type] || 'Заказ'}
                  </span>
                  <span className={`text-xs font-medium ${STATUS_LABELS[(item.data as Order).status]?.color || 'text-[var(--text-muted)]'}`}>
                    {STATUS_LABELS[(item.data as Order).status]?.label || (item.data as Order).status}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                  <span>×{(item.data as Order).quantity}</span>
                  {(item.data as Order).amount && (
                    <span className="text-emerald-400">${((item.data as Order).amount! / 100).toFixed(0)}</span>
                  )}
                  <span className="ml-auto">{formatDate(item.date)}</span>
                </div>
              </div>
            )}
            
            {item.type === 'message' && (
              <div className="p-3 rounded-xl bg-violet-500/10 border border-violet-500/20">
                <div className="text-sm text-[var(--text-secondary)] line-clamp-2">
                  {(item.data as Message).text?.slice(0, 100)}
                  {((item.data as Message).text?.length || 0) > 100 && '...'}
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-1">{formatDate(item.date)}</div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
