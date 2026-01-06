import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  getConversation, updateConversation, markConversationRead,
  createOrder, getOrders, deleteOrder, updateOrder,
  analyzeConversationOrder,
  ConversationDetail, Order 
} from '../api';
import PageWrapper from '../components/PageWrapper';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../contexts/ToastContext';
import DatePicker from '../components/DatePicker';
import Modal from '../components/Modal';

const STATUS_OPTIONS = [
  { value: 'new', label: 'Новый', icon: '✨', color: 'violet' },
  { value: 'ordered', label: 'Заказал', icon: '✅', color: 'emerald' },
  { value: 'rejected', label: 'Отказ', icon: '❌', color: 'red' },
];

const CATEGORY_OPTIONS = [
  { value: 'thumbnail', label: 'Превью', icon: '🖼️' },
  { value: 'banner', label: 'Баннер', icon: '🎨' },
  { value: 'logo', label: 'Логотип', icon: '⭐' },
  { value: 'channel_design', label: 'Оформление канала', icon: '📺' },
  { value: 'creative', label: 'Креатив', icon: '💡' },
  { value: 'other', label: 'Другое', icon: '📦' },
];

const REJECTION_REASONS = [
  { value: 'expensive', label: 'Дорого', emoji: '💸' },
  { value: 'no_prepay', label: 'Без предоплаты', emoji: '🚫' },
  { value: 'later', label: 'Позже', emoji: '⏰' },
  { value: 'competitor', label: 'Ушёл к конкуренту', emoji: '🏃' },
  { value: 'ghosted', label: 'Пропал', emoji: '👻' },
  { value: 'wrong_niche', label: 'Не моя ниша', emoji: '🎯' },
  { value: 'other', label: 'Другое', emoji: '📝' },
];

const SERVICE_TYPES = [
  { value: 'thumbnail', label: 'Превью', icon: '🖼️' },
  { value: 'banner', label: 'Баннер', icon: '🎨' },
  { value: 'logo', label: 'Логотип', icon: '⭐' },
  { value: 'channel_design', label: 'Оформление', icon: '📺' },
  { value: 'creative', label: 'Креатив', icon: '💡' },
  { value: 'other', label: 'Другое', icon: '📦' },
];

export default function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  
  // Order form state
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [orderForm, setOrderForm] = useState({
    service_type: 'thumbnail',
    quantity: 1,
    amount: '',
    has_ab_test: false,
    has_title: false,
    has_rush: false,
    deadline_type: '' as '' | 'exact' | 'flexible',
    deadline_date: '',
    deadline_range: '',
    notes: '',
  });
  const [savingOrder, setSavingOrder] = useState(false);
  const [analyzingOrder, setAnalyzingOrder] = useState(false);
  
  // Local price state for each order (to avoid saving on every keystroke)
  const [localPrices, setLocalPrices] = useState<Record<number, string>>({});
  
  // Rejection modal
  const [showRejectionModal, setShowRejectionModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rejectionCustom, setRejectionCustom] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Real-time updates
  useWebSocket('new_message', (data: any) => {
    if (data.conversation_id === Number(id)) {
      loadConversation();
    }
  });

  const loadConversation = async () => {
    if (!id) return;
    try {
      const conv = await getConversation(Number(id));
      setConversation(conv);
      
      // Load orders for this conversation with Todoist sync
      if (conv.id) {
        // First trigger board sync (this syncs with Todoist)
        try {
          await fetch('/api/orders/board', { credentials: 'include' });
        } catch (e) {
          console.error('Board sync failed:', e);
        }
        
        // Then load orders for this conversation
        const ordersResult = await getOrders({ conversation_id: conv.id });
        setOrders(ordersResult.items);
        
        // Initialize local prices
        const prices: Record<number, string> = {};
        ordersResult.items.forEach(o => {
          prices[o.id] = String(Math.round((o.amount || 0) / 100));
        });
        setLocalPrices(prices);
      }
      
      // Mark as read
      if (conv.unread_count > 0) {
        await markConversationRead(Number(id));
      }
    } catch (err) {
      console.error('Failed to load conversation:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConversation();
  }, [id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages]);

  const handleStatusChange = async (newStatus: string) => {
    if (!conversation || updating) return;
    
    // If changing to rejected, show modal
    if (newStatus === 'rejected') {
      setShowRejectionModal(true);
      return;
    }
    
    setUpdating(true);
    try {
      const updated = await updateConversation(conversation.id, { status: newStatus });
      setConversation(prev => prev ? { ...prev, ...updated } : null);
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setUpdating(false);
    }
  };

  const handleReject = async () => {
    if (!conversation || !rejectionReason) return;
    
    setUpdating(true);
    try {
      const updated = await updateConversation(conversation.id, {
        status: 'rejected',
        rejection_reason: rejectionReason,
        rejection_custom: rejectionReason === 'other' ? rejectionCustom : undefined,
      });
      setConversation(prev => prev ? { ...prev, ...updated } : null);
      setShowRejectionModal(false);
      setRejectionReason('');
      setRejectionCustom('');
    } catch (err) {
      console.error('Failed to reject:', err);
    } finally {
      setUpdating(false);
    }
  };

  const handleCategoryChange = async (category: string) => {
    if (!conversation || updating) return;
    
    setUpdating(true);
    try {
      const updated = await updateConversation(conversation.id, { category });
      setConversation(prev => prev ? { ...prev, ...updated } : null);
    } catch (err) {
      console.error('Failed to update category:', err);
    } finally {
      setUpdating(false);
    }
  };

  const handleCreateOrder = async () => {
    if (!conversation || !orderForm.amount) return;
    
    setSavingOrder(true);
    try {
      const newOrder = await createOrder({
        client_id: conversation.client_id,
        conversation_id: conversation.id,
        service_type: orderForm.service_type,
        quantity: orderForm.quantity,
        amount: Math.round(parseFloat(orderForm.amount) * 100), // Convert to cents
        has_ab_test: orderForm.has_ab_test,
        has_title: orderForm.has_title,
        has_rush: orderForm.has_rush,
        deadline_type: orderForm.deadline_type || undefined,
        deadline_date: orderForm.deadline_date || undefined,
        deadline_range: orderForm.deadline_range || undefined,
        notes: orderForm.notes || undefined,
      });
      
      setOrders(prev => [newOrder, ...prev]);
      setShowOrderForm(false);
      setOrderForm({
        service_type: 'thumbnail',
        quantity: 1,
        amount: '',
        has_ab_test: false,
        has_title: false,
        has_rush: false,
        deadline_type: '',
        deadline_date: '',
        deadline_range: '',
        notes: '',
      });
      
      // Update conversation status to ordered
      if (conversation.status === 'new') {
        await handleStatusChange('ordered');
      }
    } catch (err) {
      console.error('Failed to create order:', err);
      toast.error('Ошибка создания заказа');
    } finally {
      setSavingOrder(false);
    }
  };

  const handleDeleteOrder = async (orderId: number) => {
    try {
      await deleteOrder(orderId);
      setOrders(prev => prev.filter(o => o.id !== orderId));
      toast.success('Заказ удалён');
    } catch (err) {
      console.error('Failed to delete order:', err);
      toast.error('Ошибка удаления');
    }
  };

  const handleQuickUpdateOrder = async (orderId: number, field: string, value: any) => {
    try {
      const updated = await updateOrder(orderId, { [field]: value });
      setOrders(prev => prev.map(o => o.id === orderId ? { ...o, ...updated } : o));
      toast.success('Сохранено');
    } catch (err) {
      console.error('Failed to update order:', err);
      toast.error('Ошибка сохранения');
    }
  };

  const handlePriceBlur = async (orderId: number) => {
    const localPrice = localPrices[orderId];
    const currentAmount = orders.find(o => o.id === orderId)?.amount || 0;
    const newAmount = parseInt(localPrice || '0') * 100;
    
    if (newAmount !== currentAmount) {
      await handleQuickUpdateOrder(orderId, 'amount', newAmount);
    }
  };

  const handlePricePreset = async (orderId: number, price: number) => {
    setLocalPrices(prev => ({ ...prev, [orderId]: String(price) }));
    await handleQuickUpdateOrder(orderId, 'amount', price * 100);
  };

  const handleCompleteOrder = async (orderId: number) => {
    try {
      const updated = await updateOrder(orderId, { status: 'completed' });
      setOrders(prev => prev.map(o => o.id === orderId ? { ...o, ...updated } : o));
      toast.success('Заказ выполнен!', '✅');
    } catch (err) {
      toast.error('Ошибка');
    }
  };

  const handleAnalyzeOrder = async () => {
    if (!conversation || analyzingOrder) return;
    
    setAnalyzingOrder(true);
    try {
      const result = await analyzeConversationOrder(conversation.id);
      
      if (result.success && result.order) {
        toast.success(`Создан заказ: ${result.order.service_type} ×${result.order.quantity}`, '🤖');
        // Reload orders
        const ordersResult = await getOrders({ client_id: conversation.client_id });
        setOrders(ordersResult.items);
      } else {
        toast.warning(result.message || 'AI не обнаружил заказ');
      }
    } catch (err) {
      console.error('Failed to analyze order:', err);
      toast.error('Ошибка анализа. Попробуйте ещё раз.');
    } finally {
      setAnalyzingOrder(false);
    }
  };

  const formatMessageTime = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  // Only count active orders (exclude cancelled and deleted)
  const activeOrders = orders.filter(o => o.status !== 'cancelled' && o.status !== 'deleted');
  const totalOrdersAmount = activeOrders.reduce((sum, o) => sum + (o.amount || 0), 0) / 100;

  if (loading) {
    return (
      <PageWrapper loading={true}>
        <div />
      </PageWrapper>
    );
  }

  if (!conversation) {
    return (
      <PageWrapper loading={false}>
        <div className="text-center py-20">
          <div className="text-6xl mb-4">🔍</div>
          <h2 className="text-xl font-bold mb-2">Обращение не найдено</h2>
          <button onClick={() => navigate('/')} className="btn btn-primary mt-4">
            ← На главную
          </button>
        </div>
      </PageWrapper>
    );
  }

  const client = conversation.client;

  return (
    <PageWrapper loading={false}>
      <div className="max-w-4xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button onClick={() => navigate('/')} className="btn btn-ghost">
            ← Назад
          </button>
          
          {client?.username && (
            <a
              href={`https://t.me/${client.username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
            >
              💬 Открыть чат
            </a>
          )}
        </div>

        {/* Client info card */}
        {client && (
          <div className="card p-6 mb-6">
            <div className="flex items-start gap-5">
              {client.avatar_local_path ? (
                <img 
                  src={`http://localhost:8000${client.avatar_local_path}`}
                  alt={client.first_name}
                  className="w-16 h-16 rounded-2xl object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                  }}
                />
              ) : null}
              <div className={`avatar avatar-lg ${client.avatar_local_path ? 'hidden' : ''}`}>
                {getInitials(client.first_name)}
              </div>
              
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="text-2xl font-bold text-white">
                    {client.first_name} {client.last_name || ''}
                  </h2>
                  {client.status === 'repeat' && (
                    <span className="tag bg-blue-500/20 text-blue-400 border border-blue-500/40">🔄 Повторный</span>
                  )}
                </div>
                
                <div className="flex items-center gap-4 text-[var(--text-secondary)]">
                  {client.username && (
                    <span>@{client.username}</span>
                  )}
                  <span>•</span>
                  <span>{client.total_orders} заказов</span>
                  <span>•</span>
                  <span>${client.total_spent.toFixed(0)}</span>
                </div>
                
                {/* Sticky note */}
                {client.sticky_note && (
                  <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                    <div className="text-amber-400 text-sm font-medium mb-1">📌 Заметка:</div>
                    <div className="text-[var(--text-secondary)]">{client.sticky_note}</div>
                  </div>
                )}
              </div>
              
              <Link to={`/clients/${client.id}`} className="btn btn-secondary">
                Карточка клиента →
              </Link>
            </div>
          </div>
        )}

        {/* Status & Category */}
        <div className="card p-5 mb-6">
          <div className="flex items-center gap-4 mb-4">
            <span className="text-[var(--text-muted)] font-medium">Статус:</span>
            <div className="flex gap-2">
              {STATUS_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => handleStatusChange(opt.value)}
                  disabled={updating}
                  className={`btn btn-sm ${conversation.status === opt.value ? 'btn-primary' : 'btn-secondary'}`}
                >
                  {opt.icon} {opt.label}
                </button>
              ))}
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-[var(--text-muted)] font-medium">Категория:</span>
            <select
              value={conversation.category || ''}
              onChange={(e) => handleCategoryChange(e.target.value)}
              disabled={updating}
              className="input h-10"
              style={{ width: '200px' }}
            >
              <option value="">Не указана</option>
              {CATEGORY_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>
              ))}
            </select>
          </div>
          
          {/* Rejection reason display */}
          {conversation.status === 'rejected' && conversation.rejection_reason && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl">
              <span className="text-red-400">
                {REJECTION_REASONS.find(r => r.value === conversation.rejection_reason)?.emoji}{' '}
                Причина отказа: {REJECTION_REASONS.find(r => r.value === conversation.rejection_reason)?.label}
                {conversation.rejection_custom && ` — ${conversation.rejection_custom}`}
              </span>
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="card p-5 mb-6">
          <h3 className="text-lg font-semibold mb-4">💬 Сообщения</h3>
          
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {conversation.messages.length === 0 ? (
              <div className="text-center py-8 text-[var(--text-muted)]">
                Нет сообщений
              </div>
            ) : (
              conversation.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.direction === 'out' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`message ${msg.direction === 'in' ? 'message-in' : 'message-out'}`}>
                    <div>{msg.text || `[${msg.message_type}]`}</div>
                    <div className="message-time">{formatMessageTime(msg.sent_at)}</div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
          
          {conversation.auto_reply_sent && (
            <div className="mt-4 text-center text-sm text-[var(--text-muted)]">
              🤖 Автоответ отправлен
            </div>
          )}
        </div>

        {/* Orders */}
        <div className="card p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">📦 Заказы в этом обращении</h3>
            <div className="flex gap-2">
              <button 
                onClick={handleAnalyzeOrder} 
                disabled={analyzingOrder}
                className="btn btn-secondary btn-sm"
                title="AI проанализирует переписку и создаст заказ если найдёт"
              >
                {analyzingOrder ? '🔄 Анализ...' : '🤖 AI анализ'}
              </button>
              <button onClick={() => setShowOrderForm(true)} className="btn btn-primary btn-sm">
                + Добавить заказ
              </button>
            </div>
          </div>
          
          {orders.length === 0 ? (
            <div className="text-center py-8 text-[var(--text-muted)]">
              Нет заказов
            </div>
          ) : (
            <div className="space-y-4">
              {orders.map((order) => {
                const serviceType = SERVICE_TYPES.find(s => s.value === order.service_type);
                const isCompleted = order.status === 'completed';
                const isCancelled = order.status === 'cancelled';
                const today = new Date().toISOString().split('T')[0];
                const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
                const orderDeadline = order.deadline_date ? order.deadline_date.split('T')[0] : '';
                const currentPrice = localPrices[order.id] ?? String(Math.round((order.amount || 0) / 100));
                const PRICE_PRESETS = [10, 12, 15, 18, 20];
                
                return (
                  <div 
                    key={order.id} 
                    className={`relative rounded-2xl border overflow-hidden transition-all ${
                      isCompleted ? 'bg-emerald-500/5 border-emerald-500/30' :
                      isCancelled ? 'bg-red-500/5 border-red-500/30 opacity-60' :
                      'bg-gradient-to-br from-[var(--bg-secondary)] to-[var(--bg-tertiary)] border-[var(--border)] hover:border-violet-500/50'
                    }`}
                  >
                    <div className="p-4">
                      {/* Top row: Service type + Quantity */}
                      <div className="flex items-center gap-4 mb-4">
                        {/* Service icon */}
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${
                          isCompleted ? 'bg-emerald-500/20' :
                          isCancelled ? 'bg-red-500/20' :
                          'bg-violet-500/20'
                        }`}>
                          {serviceType?.icon || '📦'}
                        </div>
                        
                        {/* Service type dropdown */}
                        <div className="flex-1">
                          <select
                            value={order.service_type}
                            onChange={(e) => handleQuickUpdateOrder(order.id, 'service_type', e.target.value)}
                            disabled={isCompleted || isCancelled}
                            className="bg-transparent border-none text-lg font-semibold text-[var(--text-primary)] cursor-pointer hover:text-violet-400 transition-colors p-0"
                          >
                            {SERVICE_TYPES.map(opt => (
                              <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>
                            ))}
                          </select>
                          
                          {/* Upsells */}
                          {(order.has_ab_test || order.has_title || order.has_rush) && (
                            <div className="flex gap-2 mt-1">
                              {order.has_ab_test && <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">A/B</span>}
                              {order.has_title && <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400">Заголовок</span>}
                              {order.has_rush && <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400">Срочно</span>}
                            </div>
                          )}
                        </div>
                        
                        {/* Quantity with styled buttons */}
                        <div className="flex items-center gap-1 bg-[var(--bg-tertiary)] rounded-xl p-1">
                          <button
                            onClick={() => order.quantity > 1 && handleQuickUpdateOrder(order.id, 'quantity', order.quantity - 1)}
                            disabled={order.quantity <= 1 || isCompleted || isCancelled}
                            className="w-9 h-9 rounded-lg bg-violet-500/20 hover:bg-violet-500/40 text-violet-400 font-bold text-xl transition-all disabled:opacity-30 disabled:hover:bg-violet-500/20 flex items-center justify-center"
                          >
                            −
                          </button>
                          <span className="w-10 text-center font-bold text-lg text-[var(--text-primary)]">{order.quantity}</span>
                          <button
                            onClick={() => handleQuickUpdateOrder(order.id, 'quantity', order.quantity + 1)}
                            disabled={isCompleted || isCancelled}
                            className="w-9 h-9 rounded-lg bg-violet-500/20 hover:bg-violet-500/40 text-violet-400 font-bold text-xl transition-all disabled:opacity-30 disabled:hover:bg-violet-500/20 flex items-center justify-center"
                          >
                            +
                          </button>
                        </div>
                      </div>
                      
                      {/* Price row with presets */}
                      <div className="flex items-center gap-3 mb-4">
                        <span className="text-sm text-[var(--text-muted)]">💰</span>
                        <div className="flex gap-2 flex-wrap">
                          {PRICE_PRESETS.map(price => (
                            <button
                              key={price}
                              onClick={() => handlePricePreset(order.id, price)}
                              disabled={isCompleted || isCancelled}
                              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                                parseInt(currentPrice) === price
                                  ? 'bg-emerald-500 text-white'
                                  : 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                              } disabled:opacity-30`}
                            >
                              ${price}
                            </button>
                          ))}
                          {/* Custom price input */}
                          <div className="flex items-center bg-[var(--bg-tertiary)] rounded-lg px-2 py-1">
                            <span className="text-emerald-400 text-sm mr-1">$</span>
                            <input
                              type="text"
                              inputMode="numeric"
                              value={currentPrice}
                              onChange={(e) => {
                                const val = e.target.value.replace(/[^0-9]/g, '');
                                setLocalPrices(prev => ({ ...prev, [order.id]: val }));
                              }}
                              onBlur={() => handlePriceBlur(order.id)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  handlePriceBlur(order.id);
                                  (e.target as HTMLInputElement).blur();
                                }
                              }}
                              disabled={isCompleted || isCancelled}
                              className="w-14 bg-transparent border-none text-lg font-bold text-emerald-400 text-center p-0 disabled:opacity-50 focus:outline-none"
                              placeholder="0"
                            />
                          </div>
                        </div>
                      </div>
                      
                      {/* Deadline row */}
                      <div className="flex items-center gap-3 mb-4">
                        <span className="text-sm text-[var(--text-muted)]">📅</span>
                        
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleQuickUpdateOrder(order.id, 'deadline_date', today)}
                            disabled={isCompleted || isCancelled}
                            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                              orderDeadline === today
                                ? 'bg-amber-500 text-white'
                                : 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20'
                            } disabled:opacity-30`}
                          >
                            Сегодня
                          </button>
                          <button
                            onClick={() => handleQuickUpdateOrder(order.id, 'deadline_date', tomorrow)}
                            disabled={isCompleted || isCancelled}
                            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                              orderDeadline === tomorrow
                                ? 'bg-blue-500 text-white'
                                : 'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20'
                            } disabled:opacity-30`}
                          >
                            Завтра
                          </button>
                        </div>
                        
                        <input
                          type="date"
                          value={orderDeadline}
                          onChange={(e) => handleQuickUpdateOrder(order.id, 'deadline_date', e.target.value || null)}
                          disabled={isCompleted || isCancelled}
                          className="bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] disabled:opacity-30"
                        />
                        
                        {orderDeadline && (
                          <button
                            onClick={() => handleQuickUpdateOrder(order.id, 'deadline_date', null)}
                            disabled={isCompleted || isCancelled}
                            className="text-[var(--text-muted)] hover:text-red-400 transition-colors disabled:opacity-30"
                            title="Убрать дедлайн"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                      
                      {/* Bottom row: Status + Actions */}
                      <div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
                        <div className="flex gap-2">
                          {[
                            { value: 'pending', label: 'В работе', color: 'amber' },
                            { value: 'completed', label: 'Готово', color: 'emerald' },
                            { value: 'cancelled', label: 'Отменён', color: 'red' },
                          ].map(status => (
                            <button
                              key={status.value}
                              onClick={() => handleQuickUpdateOrder(order.id, 'status', status.value)}
                              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                                order.status === status.value
                                  ? status.color === 'amber' ? 'bg-amber-500 text-white' :
                                    status.color === 'emerald' ? 'bg-emerald-500 text-white' :
                                    'bg-red-500 text-white'
                                  : status.color === 'amber' ? 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20' :
                                    status.color === 'emerald' ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20' :
                                    'bg-red-500/10 text-red-400 hover:bg-red-500/20'
                              }`}
                            >
                              {status.label}
                            </button>
                          ))}
                        </div>
                        
                        {/* Action buttons */}
                        <div className="flex gap-2">
                          {order.status === 'pending' && (
                            <button
                              onClick={() => handleCompleteOrder(order.id)}
                              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 font-medium transition-colors"
                            >
                              ✓ Выполнено
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteOrder(order.id)}
                            className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                            title="Удалить заказ"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          
          {activeOrders.length > 0 && (
            <div className="mt-5 pt-4 border-t border-[var(--border)] flex items-center justify-between">
              <span className="text-[var(--text-muted)]">
                {activeOrders.length} {activeOrders.length === 1 ? 'заказ' : activeOrders.length < 5 ? 'заказа' : 'заказов'}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[var(--text-muted)]">Итого:</span>
                <span className="text-3xl font-bold text-emerald-400">${totalOrdersAmount.toFixed(0)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Order Form Modal */}
        <Modal isOpen={showOrderForm} onClose={() => setShowOrderForm(false)} contentClassName="w-full max-w-lg p-6" className="overflow-visible">
              <h3 className="text-lg font-semibold mb-4">📦 Новый заказ</h3>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Тип услуги</label>
                    <select
                      value={orderForm.service_type}
                      onChange={e => setOrderForm(f => ({ ...f, service_type: e.target.value }))}
                      className="input"
                    >
                      {SERVICE_TYPES.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Количество</label>
                    <input
                      type="number"
                      min="1"
                      value={orderForm.quantity}
                      onChange={e => setOrderForm(f => ({ ...f, quantity: parseInt(e.target.value) || 1 }))}
                      className="input"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Сумма (USD) *</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={orderForm.amount}
                    onChange={e => setOrderForm(f => ({ ...f, amount: e.target.value }))}
                    className="input"
                    placeholder="0.00"
                  />
                </div>
                
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Апсейлы</label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={orderForm.has_ab_test}
                        onChange={e => setOrderForm(f => ({ ...f, has_ab_test: e.target.checked }))}
                        className="w-4 h-4"
                      />
                      <span>A/B тест</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={orderForm.has_title}
                        onChange={e => setOrderForm(f => ({ ...f, has_title: e.target.checked }))}
                        className="w-4 h-4"
                      />
                      <span>Заголовок</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={orderForm.has_rush}
                        onChange={e => setOrderForm(f => ({ ...f, has_rush: e.target.checked }))}
                        className="w-4 h-4"
                      />
                      <span>Срочно</span>
                    </label>
                  </div>
                </div>
                
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Дедлайн</label>
                  <div className="flex gap-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setOrderForm(f => ({ ...f, deadline_type: 'exact' }))}
                      className={`btn btn-sm ${orderForm.deadline_type === 'exact' ? 'btn-primary' : 'btn-secondary'}`}
                    >
                      Точная дата
                    </button>
                    <button
                      type="button"
                      onClick={() => setOrderForm(f => ({ ...f, deadline_type: 'flexible' }))}
                      className={`btn btn-sm ${orderForm.deadline_type === 'flexible' ? 'btn-primary' : 'btn-secondary'}`}
                    >
                      Гибкий
                    </button>
                  </div>
                  
                  {orderForm.deadline_type === 'exact' && (
                    <DatePicker
                      value={orderForm.deadline_date}
                      onChange={(date) => setOrderForm(f => ({ ...f, deadline_date: date }))}
                      placeholder="Выберите дату и время"
                      showTime={true}
                    />
                  )}
                  
                  {orderForm.deadline_type === 'flexible' && (
                    <select
                      value={orderForm.deadline_range}
                      onChange={e => setOrderForm(f => ({ ...f, deadline_range: e.target.value }))}
                      className="input"
                    >
                      <option value="">Выберите срок</option>
                      <option value="today">Сегодня</option>
                      <option value="tomorrow">Завтра</option>
                      <option value="this_week">На этой неделе</option>
                      <option value="next_week">На следующей неделе</option>
                      <option value="2_weeks">2 недели</option>
                      <option value="end_of_month">До конца месяца</option>
                      <option value="no_rush">Не срочно</option>
                    </select>
                  )}
                </div>
                
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Заметки</label>
                  <textarea
                    value={orderForm.notes}
                    onChange={e => setOrderForm(f => ({ ...f, notes: e.target.value }))}
                    className="input"
                    rows={2}
                    placeholder="Дополнительная информация..."
                  />
                </div>
              </div>
              
              <div className="flex gap-2 mt-6">
                <button
                  onClick={handleCreateOrder}
                  disabled={!orderForm.amount || savingOrder}
                  className="btn btn-primary flex-1"
                >
                  {savingOrder ? '...' : '✅ Создать заказ'}
                </button>
                <button onClick={() => setShowOrderForm(false)} className="btn btn-secondary">
                  Отмена
                </button>
              </div>
        </Modal>

        {/* Rejection Modal */}
        <Modal isOpen={showRejectionModal} onClose={() => setShowRejectionModal(false)} contentClassName="w-full max-w-md p-6">
              <h3 className="text-lg font-semibold mb-4">❌ Причина отказа</h3>
              
              <div className="space-y-2 mb-4">
                {REJECTION_REASONS.map(reason => (
                  <button
                    key={reason.value}
                    onClick={() => setRejectionReason(reason.value)}
                    className={`w-full p-3 rounded-xl border text-left transition-all ${
                      rejectionReason === reason.value
                        ? 'border-red-500 bg-red-500/10'
                        : 'border-[var(--border)] hover:border-[var(--border-hover)]'
                    }`}
                  >
                    {reason.emoji} {reason.label}
                  </button>
                ))}
              </div>
              
              {rejectionReason === 'other' && (
                <textarea
                  value={rejectionCustom}
                  onChange={e => setRejectionCustom(e.target.value)}
                  className="input mb-4"
                  rows={2}
                  placeholder="Укажите причину..."
                />
              )}
              
              <div className="flex gap-2">
                <button
                  onClick={handleReject}
                  disabled={!rejectionReason || updating}
                  className="btn btn-danger flex-1"
                >
                  Подтвердить отказ
                </button>
                <button onClick={() => setShowRejectionModal(false)} className="btn btn-secondary">
                  Отмена
                </button>
              </div>
        </Modal>
      </div>
    </PageWrapper>
  );
}
