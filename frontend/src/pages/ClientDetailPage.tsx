import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  getClient, updateClient, markClientRead, sendMessage, getTemplates, getTags, 
  archiveClient, unarchiveClient, deleteClient, createReminder, completeReminder, deleteReminder,
  createOrder, updateOrder, deleteOrder, getOrders, getRejectionReasons, getOrderStats, mergeClients, searchClients,
  fetchClientAvatar,
  ClientDetail, Template, Tag, Order, RejectionReason, Client
} from '../api';
import PageWrapper from '../components/PageWrapper';
import { useWebSocket } from '../hooks/useWebSocket';
import DatePicker from '../components/DatePicker';
import Select from '../components/Select';
import Timeline from '../components/Timeline';
import Modal from '../components/Modal';
import { useToast } from '../contexts/ToastContext';

// Воронка: new → sent_price → ordered | rejected
const STATUS_OPTIONS = [
  { value: 'new', label: 'Новый', icon: '✨' },
  { value: 'sent_price', label: 'Отправлен прайс', icon: '💰' },
  { value: 'ordered', label: 'Заказал', icon: '✅' },
  { value: 'rejected', label: 'Отказ', icon: '❌' },
];

const REJECTION_REASONS_FALLBACK = [
  { code: 'expensive', label: 'Дорого', emoji: '💰' },
  { code: 'no_prepay', label: 'Не хочет предоплату', emoji: '💳' },
  { code: 'later', label: 'Сказал позже - не написал', emoji: '⏰' },
  { code: 'competitor', label: 'Ушёл к другому', emoji: '🔄' },
  { code: 'ghosted', label: 'Пропал без причины', emoji: '❓' },
  { code: 'wrong_niche', label: 'Не моя ниша (ошибся)', emoji: '🚫' },
  { code: 'other', label: 'Другое', emoji: '📝' },
];

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  
  const [client, setClient] = useState<ClientDetail | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [notes, setNotes] = useState('');
  const [editingNotes, setEditingNotes] = useState(false);
  const [savingNotes, setSavingNotes] = useState(false);
  
  // New state for additional features
  const [showLostReasonModal, setShowLostReasonModal] = useState(false);
  const [lostReason, setLostReason] = useState('');
  const [showReminderModal, setShowReminderModal] = useState(false);
  const [reminderText, setReminderText] = useState('');
  const [reminderType, setReminderType] = useState<'dm' | 'sticky'>('sticky');
  const [reminderDate, setReminderDate] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showDeadlineModal, setShowDeadlineModal] = useState(false);
  const [deadline, setDeadline] = useState('');
  
  // Orders state
  const [orders, setOrders] = useState<Order[]>([]);
  const [orderStats, setOrderStats] = useState({ total_orders: 0, completed_orders: 0, total_spent: 0 });
  const [rejectionReasons, setRejectionReasons] = useState<RejectionReason[]>([]);
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [showOrdersListModal, setShowOrdersListModal] = useState(false);
  const [editingOrder, setEditingOrder] = useState<Order | null>(null);
  const [orderForm, setOrderForm] = useState({
    service_type: 'thumbnail' as const,
    quantity: 1,
    amount: '',
    deadline_type: '' as '' | 'exact' | 'flexible',
    deadline_date: '',
    deadline_range: '',
    notes: '',
    status: 'pending' as 'pending' | 'completed' | 'cancelled',
  });

  // Merge state
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [mergeSearch, setMergeSearch] = useState('');
  const [mergeResults, setMergeResults] = useState<Client[]>([]);
  const [selectedMergeClients, setSelectedMergeClients] = useState<number[]>([]);
  const [merging, setMerging] = useState(false);

  // Timeline tab
  const [activeTab, setActiveTab] = useState<'messages' | 'timeline'>('messages');

  useEffect(() => {
    if (id) { loadClient(parseInt(id)); loadTemplates(); loadTags(); loadOrders(parseInt(id)); loadRejectionReasons(); }
  }, [id]);

  // Real-time message updates
  useWebSocket('new_message', (data) => {
    if (client && data.client_id === client.id) {
      // Add new message to the list
      setClient(prev => prev ? {
        ...prev,
        messages: [...prev.messages, data.message],
        unread_count: 0, // We're viewing, so mark as read
      } : null);
    }
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [client?.messages]);

  const loadClient = async (clientId: number) => {
    setLoading(true);
    try {
      const data = await getClient(clientId);
      setClient(data);
      setNotes(data.notes || '');
      setDeadline(data.deadline ? data.deadline.split('T')[0] : '');
      if (data.unread_count > 0) {
        await markClientRead(clientId);
        setClient(c => c ? { ...c, unread_count: 0 } : null);
      }
    } catch (err) { console.error('Failed to load client:', err); }
    finally { setLoading(false); }
  };

  const loadTemplates = async () => {
    try { const result = await getTemplates({ is_auto_reply: false }); setTemplates(result.items); }
    catch (err) { console.error('Failed to load templates:', err); }
  };

  const loadTags = async () => {
    try { const result = await getTags(); setAllTags(result.items); }
    catch (err) { console.error('Failed to load tags:', err); }
  };

  const loadOrders = async (clientId: number) => {
    try {
      const [ordersResult, statsResult] = await Promise.all([
        getOrders({ client_id: clientId }),
        getOrderStats(clientId),
      ]);
      setOrders(ordersResult.items);
      setOrderStats(statsResult);
    } catch (err) { console.error('Failed to load orders:', err); }
  };

  const loadRejectionReasons = async () => {
    try {
      const result = await getRejectionReasons();
      setRejectionReasons(result.items);
    } catch (err) {
      console.error('Failed to load rejection reasons:', err);
      setRejectionReasons(REJECTION_REASONS_FALLBACK as RejectionReason[]);
    }
  };

  // Merge search
  useEffect(() => {
    if (!mergeSearch.trim() || !showMergeModal) {
      setMergeResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const result = await searchClients(mergeSearch);
        // Exclude current client
        setMergeResults(result.items.filter(c => c.id !== client?.id));
      } catch (err) {
        console.error('Search failed:', err);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [mergeSearch, showMergeModal, client?.id]);

  const handleMerge = async () => {
    if (!client || selectedMergeClients.length === 0) return;
    setMerging(true);
    try {
      const merged = await mergeClients(selectedMergeClients, client.id);
      setClient(merged);
      setShowMergeModal(false);
      setSelectedMergeClients([]);
      setMergeSearch('');
      // Reload orders
      loadOrders(client.id);
    } catch (err) {
      console.error('Merge failed:', err);
      alert('Ошибка объединения');
    } finally {
      setMerging(false);
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!client) return;
    if (status === 'rejected') {
      setShowLostReasonModal(true);
      return;
    }
    try { const updated = await updateClient(client.id, { status }); setClient(updated); }
    catch (err) { console.error('Failed to update status:', err); }
  };

  const handleLostReasonSubmit = async () => {
    if (!client) return;
    try {
      const updated = await updateClient(client.id, { status: 'rejected', lost_reason: lostReason });
      setClient(updated);
      setShowLostReasonModal(false);
      setLostReason('');
    } catch (err) { console.error('Failed to update status:', err); }
  };

  const handleCreateOrder = async () => {
    if (!client || orderForm.quantity < 1) return;
    try {
      const newOrder = await createOrder({
        client_id: client.id,
        service_type: orderForm.service_type,
        quantity: orderForm.quantity,
        amount: orderForm.amount ? parseInt(orderForm.amount) * 100 : undefined, // convert to cents
        deadline_type: orderForm.deadline_type || undefined,
        deadline_date: orderForm.deadline_type === 'exact' && orderForm.deadline_date ? orderForm.deadline_date : undefined,
        deadline_range: orderForm.deadline_type === 'flexible' && orderForm.deadline_range ? orderForm.deadline_range : undefined,
        notes: orderForm.notes || undefined,
      });
      setOrders([newOrder, ...orders]);
      setOrderStats(s => ({ ...s, total_orders: s.total_orders + 1 }));
      // Auto-update client status to "ordered"
      if (client.status !== 'ordered') {
        const updated = await updateClient(client.id, { status: 'ordered' });
        setClient(updated);
      }
      setShowOrderModal(false);
      setOrderForm({ service_type: 'thumbnail', quantity: 1, amount: '', deadline_type: '', deadline_date: '', deadline_range: '', notes: '', status: 'pending' });
      toast.success('Заказ создан!', '📦');
    } catch (err) { 
      console.error('Failed to create order:', err); 
      toast.error('Ошибка создания заказа');
    }
  };

  const handleEditOrder = (order: Order) => {
    setEditingOrder(order);
    setOrderForm({
      service_type: order.service_type as any,
      quantity: order.quantity,
      amount: order.amount ? String(order.amount / 100) : '',
      deadline_type: order.deadline_type || '',
      deadline_date: order.deadline_date || '',
      deadline_range: order.deadline_range || '',
      notes: order.notes || '',
      status: order.status as any,
    });
    setShowOrdersListModal(false);
    setShowOrderModal(true);
  };

  const handleUpdateOrder = async () => {
    if (!editingOrder || orderForm.quantity < 1) return;
    try {
      const updated = await updateOrder(editingOrder.id, {
        service_type: orderForm.service_type,
        quantity: orderForm.quantity,
        amount: orderForm.amount ? parseInt(orderForm.amount) * 100 : undefined,
        deadline_type: orderForm.deadline_type || undefined,
        deadline_date: orderForm.deadline_type === 'exact' && orderForm.deadline_date ? orderForm.deadline_date : undefined,
        deadline_range: orderForm.deadline_type === 'flexible' && orderForm.deadline_range ? orderForm.deadline_range : undefined,
        notes: orderForm.notes || undefined,
        status: orderForm.status,
      });
      setOrders(orders.map(o => o.id === updated.id ? updated : o));
      if (orderForm.status === 'completed' && editingOrder.status !== 'completed') {
        setOrderStats(s => ({ ...s, completed_orders: s.completed_orders + 1, total_spent: s.total_spent + (updated.amount || 0) }));
      }
      setShowOrderModal(false);
      setEditingOrder(null);
      setOrderForm({ service_type: 'thumbnail', quantity: 1, amount: '', deadline_type: '', deadline_date: '', deadline_range: '', notes: '', status: 'pending' });
      toast.success('Заказ обновлён', '✅');
    } catch (err) { 
      console.error('Failed to update order:', err); 
      toast.error('Ошибка обновления');
    }
  };

  const handleDeleteOrder = async (orderId: number) => {
    if (!confirm('Удалить этот заказ?')) return;
    try {
      await deleteOrder(orderId);
      setOrders(orders.filter(o => o.id !== orderId));
      setOrderStats(s => ({ ...s, total_orders: s.total_orders - 1 }));
    } catch (err) { console.error('Failed to delete order:', err); }
  };

  const resetOrderForm = () => {
    setEditingOrder(null);
    setOrderForm({ service_type: 'thumbnail', quantity: 1, amount: '', deadline_type: '', deadline_date: '', deadline_range: '', notes: '', status: 'pending' });
  };

  const handleTagToggle = async (tagId: number) => {
    if (!client) return;
    const currentTagIds = client.tags.map(t => t.id);
    const newTagIds = currentTagIds.includes(tagId) ? currentTagIds.filter(id => id !== tagId) : [...currentTagIds, tagId];
    try { const updated = await updateClient(client.id, { tag_ids: newTagIds }); setClient(updated); }
    catch (err) { console.error('Failed to update tags:', err); }
  };

  const handleSaveNotes = async () => {
    if (!client) return;
    setSavingNotes(true);
    try { 
      const updated = await updateClient(client.id, { notes }); 
      setClient(updated);
      setEditingNotes(false); 
    }
    catch (err) { console.error('Failed to save notes:', err); }
    finally { setSavingNotes(false); }
  };

  const handleSendMessage = async () => {
    if (!client || !message.trim() || sending) return;
    setSending(true);
    const msgText = message.trim();
    setMessage('');
    
    try {
      const newMessage = await sendMessage(client.id, msgText);
      setClient(c => c ? { ...c, messages: [...c.messages, newMessage], last_message_at: newMessage.sent_at } : null);
      inputRef.current?.focus();
    } catch (err) { 
      setMessage(msgText);
      toast.error('Не удалось отправить сообщение');
    }
    finally { setSending(false); }
  };

  const handleTemplateSelect = (template: Template) => {
    if (!client) return;
    let content = template.content;
    content = content.replace(/{first_name}/g, client.first_name);
    content = content.replace(/{username}/g, client.username || '');
    setMessage(content);
    setShowTemplates(false);
    inputRef.current?.focus();
    toast.info(`Шаблон "${template.name}" применён`, '📝');
  };

  const handleArchive = async () => {
    if (!client) return;
    try {
      await archiveClient(client.id);
      toast.success('Клиент архивирован', '📦');
      navigate('/');
    } catch (err) { toast.error('Ошибка архивации'); }
  };

  const handleUnarchive = async () => {
    if (!client) return;
    try {
      await unarchiveClient(client.id);
      setClient(c => c ? { ...c, is_archived: false } : null);
      toast.success('Клиент разархивирован', '📤');
    } catch (err) { toast.error('Ошибка разархивации'); }
  };

  const handleDelete = async () => {
    if (!client) return;
    try {
      await deleteClient(client.id);
      toast.success('Клиент удалён', '🗑️');
      navigate('/');
    } catch (err) { toast.error('Ошибка удаления'); }
  };

  const handleCreateReminder = async () => {
    if (!client || !reminderText.trim() || !reminderDate) return;
    try {
      const reminder = await createReminder({
        client_id: client.id,
        reminder_type: reminderType,
        text: reminderText,
        remind_at: new Date(reminderDate).toISOString(),
      });
      setClient(c => c ? { ...c, reminders: [...(c.reminders || []), reminder] } : null);
      setShowReminderModal(false);
      setReminderText('');
      setReminderDate('');
      toast.success('Напоминание создано', '⏰');
    } catch (err) { toast.error('Ошибка создания напоминания'); }
  };

  const handleCompleteReminder = async (reminderId: number) => {
    try {
      await completeReminder(reminderId);
      setClient(c => c ? { 
        ...c, 
        reminders: c.reminders?.map(r => r.id === reminderId ? { ...r, is_completed: true } : r) || []
      } : null);
      toast.success('Напоминание выполнено', '✅');
    } catch (err) { toast.error('Ошибка'); }
  };

  const handleDeleteReminder = async (reminderId: number) => {
    try {
      await deleteReminder(reminderId);
      setClient(c => c ? { ...c, reminders: c.reminders?.filter(r => r.id !== reminderId) || [] } : null);
    } catch (err) { toast.error('Ошибка удаления'); }
  };

  const handleSaveDeadline = async () => {
    if (!client) return;
    try {
      const updated = await updateClient(client.id, { deadline: deadline ? new Date(deadline).toISOString() : undefined });
      setClient(updated);
      setShowDeadlineModal(false);
      toast.success(deadline ? 'Дедлайн установлен' : 'Дедлайн удалён', '📅');
    } catch (err) { toast.error('Ошибка сохранения'); }
  };

  const formatTime = (dateStr: string) => {
    // Parse as UTC (backend returns UTC without Z suffix)
    const date = dateStr.endsWith('Z') ? new Date(dateStr) : new Date(dateStr + 'Z');
    return date.toLocaleTimeString('ru-RU', { timeZone: 'Asia/Tbilisi', hour: '2-digit', minute: '2-digit' });
  };
  const formatDate = (dateStr: string) => {
    // Parse as UTC
    const date = dateStr.endsWith('Z') ? new Date(dateStr) : new Date(dateStr + 'Z');
    const todayInGeorgia = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Tbilisi' }));
    const yesterdayInGeorgia = new Date(todayInGeorgia);
    yesterdayInGeorgia.setDate(yesterdayInGeorgia.getDate() - 1);
    const dateInGeorgia = new Date(date.toLocaleString('en-US', { timeZone: 'Asia/Tbilisi' }));
    if (dateInGeorgia.toDateString() === todayInGeorgia.toDateString()) return 'Сегодня';
    if (dateInGeorgia.toDateString() === yesterdayInGeorgia.toDateString()) return 'Вчера';
    return date.toLocaleDateString('ru-RU', { timeZone: 'Asia/Tbilisi', month: 'short', day: 'numeric', year: 'numeric' });
  };
  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  if (loading) {
    return (
      <div className="max-w-6xl">
        <div className="mb-6"><div className="skeleton h-10 w-32 rounded-lg" /></div>
        <div className="grid grid-cols-3 gap-6">
          <div className="space-y-6">
            <div className="card p-6">
              <div className="flex items-center gap-4 mb-6"><div className="skeleton w-16 h-16 rounded-2xl" /><div><div className="skeleton h-6 w-40 mb-2" /><div className="skeleton h-4 w-28" /></div></div>
              <div className="skeleton h-32" />
            </div>
          </div>
          <div className="col-span-2"><div className="card h-[600px]"><div className="skeleton h-full" /></div></div>
        </div>
      </div>
    );
  }

  if (!client) {
    return (
      <div className="max-w-6xl">
        <div className="card card-gradient">
          <div className="empty-state py-20">
            <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-red-500/20 to-rose-500/10 flex items-center justify-center text-5xl mb-6 mx-auto">😕</div>
            <div className="empty-state-title text-2xl mb-2">Клиент не найден</div>
            <button type="button" onClick={() => navigate('/')} className="btn btn-primary mt-4">← К клиентам</button>
          </div>
        </div>
      </div>
    );
  }

  const pendingReminders = client.reminders?.filter(r => !r.is_completed) || [];

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-6xl">
        {/* Back button and actions */}
      <div className="flex items-center justify-between mb-6">
        <button type="button" onClick={() => navigate('/')} className="btn btn-ghost -ml-3">← К клиентам</button>
        <div className="flex gap-2">
          <button type="button" onClick={() => setShowOrderModal(true)} className="btn btn-primary">📦 Создать заказ</button>
          <button type="button" onClick={() => setShowReminderModal(true)} className="btn btn-secondary">⏰ Напоминание</button>
          <button type="button" onClick={() => setShowDeadlineModal(true)} className="btn btn-secondary">📅 Дедлайн</button>
          <button type="button" onClick={() => setShowMergeModal(true)} className="btn btn-secondary">🔗 Объединить</button>
          {client?.is_archived ? (
            <button type="button" onClick={handleUnarchive} className="btn btn-success">📤 Разархивировать</button>
          ) : (
            <button type="button" onClick={handleArchive} className="btn btn-secondary">📦 Архив</button>
          )}
          <button type="button" onClick={() => setShowDeleteConfirm(true)} className="btn btn-danger">🗑️ Удалить</button>
        </div>
      </div>

      {/* Archived banner */}
      {client?.is_archived && (
        <div className="card p-4 mb-6 border-l-4 border-amber-500 bg-amber-500/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-amber-500">📦</span>
              <span className="font-semibold text-amber-200">Клиент в архиве</span>
            </div>
            <button type="button" onClick={handleUnarchive} className="btn btn-sm btn-success">
              📤 Разархивировать
            </button>
          </div>
        </div>
      )}

      {/* Pending reminders banner */}
      {pendingReminders.length > 0 && (
        <div className="card p-4 mb-6 border-l-4 border-amber-500 bg-amber-500/10">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-amber-500">⏰</span>
            <span className="font-semibold text-amber-200">Активные напоминания</span>
          </div>
          {pendingReminders.map(r => (
            <div key={r.id} className="flex items-center justify-between py-2 border-b border-amber-500/20 last:border-0">
              <div>
                <span className="text-sm">{r.text}</span>
                <span className="text-xs text-[var(--text-muted)] ml-2">({r.reminder_type === 'dm' ? 'Отправить ЛС' : 'Заметка'})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--text-muted)]">{formatDate(r.remind_at)}</span>
                <button type="button" onClick={() => handleCompleteReminder(r.id)} className="btn btn-sm btn-success">✓</button>
                <button type="button" onClick={() => handleDeleteReminder(r.id)} className="btn btn-sm btn-ghost">×</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Left column */}
        <div className="space-y-6">
          {/* Profile */}
          <div className="card p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="relative group">
                {client.avatar_local_path ? (
                  <img 
                    src={`http://localhost:8000${client.avatar_local_path}`}
                    alt={client.first_name}
                    className="w-16 h-16 rounded-2xl object-cover"
                  />
                ) : (
                  <div className="avatar avatar-lg">
                    {getInitials(client.first_name)}
                  </div>
                )}
                {/* Fetch avatar button */}
                {client.telegram_user_id > 0 && !client.avatar_local_path && (
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const result = await fetchClientAvatar(client.id);
                        if (result.success && result.avatar_url) {
                          setClient(c => c ? { ...c, avatar_local_path: result.avatar_url! } : null);
                        }
                      } catch (e) {
                        console.error('Failed to fetch avatar:', e);
                      }
                    }}
                    className="absolute inset-0 bg-black/50 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs"
                  >
                    📷
                  </button>
                )}
              </div>
              <div>
                <h1 className="text-xl font-bold gradient-text">{client.first_name} {client.last_name || ''}</h1>
                <p className="text-[var(--text-muted)]">{client.username ? `@${client.username}` : `ID: ${client.telegram_user_id}`}</p>
              </div>
            </div>

            {/* Deadline */}
            {client.deadline && (
              <div className="mb-4 p-3 rounded-xl bg-blue-500/10 border border-blue-500/30">
                <span className="text-xs text-blue-400 font-semibold">📅 Дедлайн:</span>
                <span className="ml-2 text-blue-200">{formatDate(client.deadline)}</span>
              </div>
            )}

            {/* Order stats */}
            {orderStats.total_orders > 0 && (
              <button
                type="button"
                onClick={() => setShowOrdersListModal(true)}
                className="w-full mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors text-left"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-emerald-400 font-semibold">📊 Заказы:</span>
                  <span className="text-emerald-200 font-bold">{orderStats.total_orders}</span>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs text-emerald-400">💰 Всего:</span>
                  <span className="text-emerald-200">${(orderStats.total_spent / 100).toFixed(0)}</span>
                </div>
                <div className="text-xs text-emerald-400/60 mt-2 text-center">Нажмите для просмотра →</div>
              </button>
            )}

            {/* Rejection reason */}
            {client.status === 'rejected' && client.lost_reason && (
              <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30">
                <span className="text-xs text-red-400 font-semibold">❌ Причина отказа:</span>
                <span className="ml-2 text-red-200">{client.lost_reason}</span>
              </div>
            )}

            {/* Status */}
            <div className="mb-6">
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">Статус</label>
              <div className="flex flex-wrap gap-2">
                {STATUS_OPTIONS.map(s => (
                  <button 
                    key={s.value} 
                    type="button"
                    onClick={() => handleStatusChange(s.value)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${client.status === s.value ? 'ring-2 ring-[var(--accent)] bg-[var(--accent)]/20 text-white' : 'bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'}`}>
                    <span>{s.icon}</span> {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Tags */}
            <div className="mb-6">
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">Теги</label>
              <div className="flex flex-wrap gap-2">
                {allTags.map(tag => {
                  const isActive = client.tags.some(t => t.id === tag.id);
                  return (
                    <button 
                      key={tag.id} 
                      type="button"
                      onClick={() => handleTagToggle(tag.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors border ${isActive ? 'opacity-100' : 'opacity-50 hover:opacity-80'}`}
                      style={{ backgroundColor: tag.color + (isActive ? '35' : '15'), color: tag.color, borderColor: tag.color + (isActive ? '60' : '30') }}>
                      {tag.name}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">Заметки</label>
              {editingNotes ? (
                <div className="space-y-3">
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="input" rows={4} placeholder="Добавить заметку..." autoFocus />
                  <div className="flex gap-2">
                    <button type="button" onClick={handleSaveNotes} disabled={savingNotes} className="btn btn-primary btn-sm">{savingNotes ? 'Сохранение...' : '✓ Сохранить'}</button>
                    <button type="button" onClick={() => { setNotes(client.notes || ''); setEditingNotes(false); }} className="btn btn-secondary btn-sm">Отмена</button>
                  </div>
                </div>
              ) : (
                <div onClick={() => setEditingNotes(true)} className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] cursor-pointer hover:border-[var(--accent)]/50 hover:bg-[var(--bg-hover)] transition-colors min-h-[80px]">
                  {client.notes || <span className="text-[var(--text-muted)]">Нажмите, чтобы добавить заметку...</span>}
                </div>
              )}
            </div>
          </div>

          {/* Details */}
          <div className="card p-6">
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-4">Информация</h3>
            <div className="space-y-4 text-sm">
              {[
                { label: 'Источник', value: client.source || 'telegram-business', icon: '📱' },
                { label: 'Язык', value: client.language_code?.toUpperCase() || '—', icon: '🌍' },
                { label: 'Создан', value: (client.created_at.endsWith('Z') ? new Date(client.created_at) : new Date(client.created_at + 'Z')).toLocaleDateString('ru-RU', { timeZone: 'Asia/Tbilisi' }), icon: '📅' },
              ].map(item => (
                <div key={item.label} className="flex items-center justify-between p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)]">
                  <span className="text-[var(--text-muted)] flex items-center gap-2"><span>{item.icon}</span>{item.label}</span>
                  <span className="font-medium">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column - Messages */}
        <div className="col-span-2">
          <div className="card flex flex-col h-[calc(100vh-200px)]">
            {/* Header with tabs */}
            <div className="p-5 border-b border-[var(--border)]">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-semibold text-lg">
                    {activeTab === 'messages' ? 'Сообщения' : 'История'}
                  </h2>
                  <p className="text-sm text-[var(--text-muted)]">
                    {activeTab === 'messages' ? `${client.messages.length} сообщений` : `${orders.filter(o => o.status !== 'cancelled' && o.status !== 'deleted').length} заказов`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-sm text-[var(--text-muted)]">Онлайн</span>
                </div>
              </div>
              
              {/* Tabs */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('messages')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'messages'
                      ? 'bg-[var(--accent)] text-white'
                      : 'bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  💬 Сообщения
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('timeline')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'timeline'
                      ? 'bg-[var(--accent)] text-white'
                      : 'bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  📋 История
                </button>
              </div>
            </div>

            {/* Content */}
            {activeTab === 'messages' ? (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {client.messages.length === 0 ? (
                <div className="empty-state py-16">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-500/10 flex items-center justify-center text-4xl mb-4 mx-auto">💬</div>
                  <div className="empty-state-title">Нет сообщений</div>
                  <div className="empty-state-text">Отправьте сообщение, чтобы начать диалог</div>
                </div>
              ) : (
                <>
                  {client.messages.map((msg, idx) => {
                    const prevMsg = client.messages[idx - 1];
                    const showDate = !prevMsg || formatDate(msg.sent_at) !== formatDate(prevMsg.sent_at);
                    return (
                      <div key={msg.id}>
                        {showDate && (
                          <div className="flex justify-center my-6">
                            <span className="text-xs text-[var(--text-muted)] bg-[var(--bg-secondary)] px-4 py-1.5 rounded-full border border-[var(--border)]">{formatDate(msg.sent_at)}</span>
                          </div>
                        )}
                        <div className={`flex ${msg.direction === 'out' ? 'justify-end' : 'justify-start'}`}>
                          <div className={`message ${msg.direction === 'out' ? 'message-out' : 'message-in'}`}>
                            <div className="whitespace-pre-wrap">{msg.text}</div>
                            <div className="message-time">{formatTime(msg.sent_at)}</div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Composer */}
            <div className="p-5 border-t border-[var(--border)] bg-[var(--bg-secondary)]/50">
              {showTemplates && templates.length > 0 && (
                <div className="mb-4 p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border)] max-h-48 overflow-y-auto">
                  <p className="text-xs text-[var(--text-muted)] px-2 mb-2 font-semibold uppercase tracking-wider">Быстрые шаблоны</p>
                  {templates.map(tpl => (
                    <button key={tpl.id} type="button" onClick={() => handleTemplateSelect(tpl)} className="w-full text-left px-3 py-3 rounded-lg hover:bg-[var(--bg-hover)] transition-colors text-sm">
                      <div className="font-medium hover:text-[var(--accent)] transition-colors">{tpl.name}</div>
                      <div className="text-xs text-[var(--text-muted)] truncate">{tpl.content.slice(0, 60)}...</div>
                    </button>
                  ))}
                </div>
              )}
              
              <div className="flex gap-3">
                <button type="button" onClick={() => setShowTemplates(!showTemplates)} className={`w-11 h-11 rounded-xl flex items-center justify-center text-lg transition-colors ${showTemplates ? 'bg-[var(--accent)] text-white' : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'}`}>📝</button>
                <input ref={inputRef} type="text" value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()} placeholder="Введите сообщение..." className="input flex-1" disabled={sending} />
                <button type="button" onClick={handleSendMessage} disabled={sending || !message.trim()} className="btn btn-primary px-6">
                  {sending ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <>Отправить <span className="ml-1">→</span></>}
                </button>
              </div>
            </div>
              </>
            ) : (
              /* Timeline tab */
              <div className="flex-1 overflow-y-auto p-5">
                <Timeline orders={orders} messages={client.messages} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Rejection Reason Modal */}
      <Modal isOpen={showLostReasonModal} onClose={() => setShowLostReasonModal(false)} contentClassName="w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">❌ Причина отказа</h3>
            <div className="space-y-2 mb-4">
              {(rejectionReasons.length > 0 ? rejectionReasons : REJECTION_REASONS_FALLBACK).map(reason => (
                <button key={reason.code} type="button" onClick={() => setLostReason(reason.label)} className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${lostReason === reason.label ? 'border-[var(--accent)] bg-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                  {reason.emoji} {reason.label}
                </button>
              ))}
            </div>
            <input type="text" value={lostReason} onChange={e => setLostReason(e.target.value)} placeholder="Или введите свою причину..." className="input mb-4" />
            <div className="flex gap-2">
              <button type="button" onClick={handleLostReasonSubmit} disabled={!lostReason} className="btn btn-primary flex-1">Сохранить</button>
              <button type="button" onClick={() => setShowLostReasonModal(false)} className="btn btn-secondary">Отмена</button>
            </div>
      </Modal>

      {/* Reminder Modal */}
      <Modal isOpen={showReminderModal} onClose={() => setShowReminderModal(false)} contentClassName="w-full max-w-md p-6 animate-fadeIn">
            <h3 className="text-lg font-semibold mb-4">⏰ Создать напоминание</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Тип</label>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setReminderType('sticky')} className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${reminderType === 'sticky' ? 'border-[var(--accent)] bg-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                    📌 Заметка<br/><span className="text-xs text-[var(--text-muted)]">Показать при открытии клиента</span>
                  </button>
                  <button type="button" onClick={() => setReminderType('dm')} className={`flex-1 px-4 py-3 rounded-lg border transition-colors ${reminderType === 'dm' ? 'border-[var(--accent)] bg-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                    💬 Отправить ЛС<br/><span className="text-xs text-[var(--text-muted)]">Авто-отправка сообщения</span>
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Сообщение</label>
                <textarea value={reminderText} onChange={e => setReminderText(e.target.value)} className="input" rows={3} placeholder="Текст напоминания..." />
              </div>
              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Когда</label>
                <DatePicker
                  value={reminderDate}
                  onChange={setReminderDate}
                  placeholder="Выберите дату и время"
                  minDate={new Date().toISOString().split('T')[0]}
                  showTime={true}
                />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button type="button" onClick={handleCreateReminder} disabled={!reminderText || !reminderDate} className="btn btn-primary flex-1">Создать</button>
              <button type="button" onClick={() => setShowReminderModal(false)} className="btn btn-secondary">Отмена</button>
            </div>
      </Modal>

      {/* Deadline Modal */}
      <Modal isOpen={showDeadlineModal} onClose={() => setShowDeadlineModal(false)} contentClassName="w-full max-w-md p-6 animate-fadeIn">
            <h3 className="text-lg font-semibold mb-4">📅 Установить дедлайн</h3>
            <DatePicker
              value={deadline}
              onChange={setDeadline}
              placeholder="Выберите дату дедлайна"
              minDate={new Date().toISOString().split('T')[0]}
            />
            <div className="flex gap-2 mt-6">
              <button type="button" onClick={handleSaveDeadline} className="btn btn-primary flex-1">Сохранить</button>
              <button type="button" onClick={() => { setDeadline(''); handleSaveDeadline(); }} className="btn btn-secondary">Очистить</button>
              <button type="button" onClick={() => setShowDeadlineModal(false)} className="btn btn-ghost">Отмена</button>
            </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={showDeleteConfirm} onClose={() => setShowDeleteConfirm(false)} contentClassName="w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-2">🗑️ Удалить клиента?</h3>
            <p className="text-[var(--text-secondary)] mb-6">Это навсегда удалит {client.first_name} и все сообщения. Действие нельзя отменить.</p>
            <div className="flex gap-2">
              <button type="button" onClick={handleDelete} className="btn btn-danger flex-1">Да, удалить</button>
              <button type="button" onClick={() => setShowDeleteConfirm(false)} className="btn btn-secondary flex-1">Отмена</button>
            </div>
      </Modal>

      {/* Create/Edit Order Modal */}
      <Modal isOpen={showOrderModal} onClose={() => { setShowOrderModal(false); resetOrderForm(); }} contentClassName="w-full max-w-lg" className="overflow-visible">
            <div className="p-6">
              <h3 className="text-lg font-semibold mb-4">{editingOrder ? '✏️ Редактировать заказ' : '📦 Новый заказ'}</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Тип работы *</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { value: 'thumbnail', label: 'Превью', icon: '🎨' },
                      { value: 'banner', label: 'Баннер', icon: '🖼️' },
                      { value: 'logo', label: 'Лого', icon: '✨' },
                    ].map(opt => (
                      <button key={opt.value} type="button" onClick={() => setOrderForm(f => ({ ...f, service_type: opt.value as any }))} className={`px-3 py-2 rounded-lg border text-sm transition-all ${orderForm.service_type === opt.value ? 'border-[var(--accent)] bg-[var(--accent)]/20 shadow-lg shadow-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                        {opt.icon} {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Количество *</label>
                    <input type="number" min="1" value={orderForm.quantity} onChange={e => setOrderForm(f => ({ ...f, quantity: parseInt(e.target.value) || 1 }))} className="input" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Сумма ($) *</label>
                    <input type="number" min="0" value={orderForm.amount} onChange={e => setOrderForm(f => ({ ...f, amount: e.target.value }))} className="input" placeholder="Введите сумму" />
                  </div>
                </div>

                {editingOrder && (
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Статус</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'pending', label: 'В работе', icon: '⏳' },
                        { value: 'completed', label: 'Выполнен', icon: '✅' },
                        { value: 'cancelled', label: 'Отменён', icon: '❌' },
                      ].map(opt => (
                        <button key={opt.value} type="button" onClick={() => setOrderForm(f => ({ ...f, status: opt.value as any }))} className={`px-3 py-2 rounded-lg border text-sm transition-all ${orderForm.status === opt.value ? 'border-[var(--accent)] bg-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                          {opt.icon} {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Дедлайн</label>
                  <div className="flex gap-2 mb-3">
                    <button type="button" onClick={() => setOrderForm(f => ({ ...f, deadline_type: f.deadline_type === 'exact' ? '' : 'exact' }))} className={`flex-1 px-3 py-2 rounded-lg border text-sm transition-all ${orderForm.deadline_type === 'exact' ? 'border-[var(--accent)] bg-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                      📅 Точная дата
                    </button>
                    <button type="button" onClick={() => setOrderForm(f => ({ ...f, deadline_type: f.deadline_type === 'flexible' ? '' : 'flexible' }))} className={`flex-1 px-3 py-2 rounded-lg border text-sm transition-all ${orderForm.deadline_type === 'flexible' ? 'border-[var(--accent)] bg-[var(--accent)]/20' : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'}`}>
                      🕐 Гибкий
                    </button>
                  </div>
                  {orderForm.deadline_type === 'exact' && (
                    <div style={{ position: 'relative', zIndex: 100 }}>
                      <DatePicker
                        value={orderForm.deadline_date}
                        onChange={(date) => setOrderForm(f => ({ ...f, deadline_date: date }))}
                        placeholder="Выберите дату и время"
                        minDate={new Date().toISOString().split('T')[0]}
                        showTime={true}
                      />
                    </div>
                  )}
                  {orderForm.deadline_type === 'flexible' && (
                    <Select
                      value={orderForm.deadline_range}
                      onChange={(val) => setOrderForm(f => ({ ...f, deadline_range: val }))}
                      placeholder="Выберите срок"
                      options={[
                        { value: 'today', label: 'Сегодня', icon: '📍' },
                        { value: 'tomorrow', label: 'Завтра', icon: '🌅' },
                        { value: 'this_week', label: 'На этой неделе', icon: '📆' },
                        { value: 'next_week', label: 'На следующей неделе', icon: '📅' },
                        { value: 'end_of_month', label: 'До конца месяца', icon: '🗓️' },
                        { value: '2_weeks', label: 'В течение 2 недель', icon: '⏳' },
                        { value: 'no_rush', label: 'Без срочности', icon: '🐢' },
                      ]}
                    />
                  )}
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Комментарий</label>
                  <textarea value={orderForm.notes} onChange={e => setOrderForm(f => ({ ...f, notes: e.target.value }))} className="input" rows={2} placeholder="Дополнительная информация..." />
                </div>
              </div>
              <div className="flex gap-2 mt-6">
                <button 
                  type="button" 
                  onClick={editingOrder ? handleUpdateOrder : handleCreateOrder} 
                  disabled={orderForm.quantity < 1}
                  className="btn btn-primary flex-1"
                >
                  {editingOrder ? '💾 Сохранить' : '✅ Создать заказ'}
                </button>
                <button type="button" onClick={() => { setShowOrderModal(false); resetOrderForm(); }} className="btn btn-secondary">Отмена</button>
              </div>
            </div>
      </Modal>

      {/* Orders List Modal */}
      <Modal isOpen={showOrdersListModal} onClose={() => setShowOrdersListModal(false)} contentClassName="w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-[var(--border)] flex items-center justify-between">
              <h3 className="text-lg font-semibold">📦 Заказы клиента</h3>
              <button type="button" onClick={() => setShowOrdersListModal(false)} className="btn btn-icon btn-ghost">✕</button>
            </div>
            <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(80vh - 140px)' }}>
              {orders.length === 0 ? (
                <div className="text-center py-8 text-[var(--text-muted)]">
                  <div className="text-4xl mb-2">📦</div>
                  <div>Заказов пока нет</div>
                </div>
              ) : (
                <div className="space-y-3">
                  {orders.map(order => {
                    const serviceTypes: Record<string, { label: string; icon: string }> = {
                      thumbnail: { label: 'Превью', icon: '🎨' },
                      banner: { label: 'Баннер', icon: '🖼️' },
                      logo: { label: 'Лого', icon: '✨' },
                      channel_design: { label: 'Дизайн канала', icon: '📺' },
                      other: { label: 'Другое', icon: '📝' },
                    };
                    const statusStyles: Record<string, string> = {
                      pending: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
                      completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
                      cancelled: 'bg-red-500/20 text-red-400 border-red-500/40',
                      refunded: 'bg-gray-500/20 text-gray-400 border-gray-500/40',
                    };
                    const statusLabels: Record<string, string> = {
                      pending: '⏳ В работе',
                      completed: '✅ Выполнен',
                      cancelled: '❌ Отменён',
                      refunded: '↩️ Возврат',
                    };
                    const service = serviceTypes[order.service_type] || serviceTypes.other;
                    
                    return (
                      <div key={order.id} className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] hover:border-[var(--accent)]/50 transition-colors">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">{service.icon}</span>
                            <div>
                              <div className="font-semibold">{service.label} × {order.quantity}</div>
                              <div className="text-sm text-[var(--text-muted)]">
                                {(order.created_at.endsWith('Z') ? new Date(order.created_at) : new Date(order.created_at + 'Z')).toLocaleDateString('ru-RU', { timeZone: 'Asia/Tbilisi' })}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold text-lg">${order.amount ? (order.amount / 100).toFixed(0) : 0}</div>
                            <span className={`text-xs px-2 py-1 rounded-full border ${statusStyles[order.status]}`}>
                              {statusLabels[order.status]}
                            </span>
                          </div>
                        </div>
                        
                        {order.deadline_calculated && (
                          <div className="text-sm text-[var(--text-muted)] mb-2">
                            📅 Дедлайн: {(order.deadline_calculated.endsWith('Z') ? new Date(order.deadline_calculated) : new Date(order.deadline_calculated + 'Z')).toLocaleDateString('ru-RU', { timeZone: 'Asia/Tbilisi' })}
                          </div>
                        )}
                        
                        {order.notes && (
                          <div className="text-sm text-[var(--text-secondary)] mb-3 p-2 rounded-lg bg-[var(--bg-hover)]">
                            💬 {order.notes}
                          </div>
                        )}
                        
                        <div className="flex gap-2 pt-2 border-t border-[var(--border)]">
                          <button
                            type="button"
                            onClick={() => handleEditOrder(order)}
                            className="btn btn-sm btn-secondary flex-1"
                          >
                            ✏️ Редактировать
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteOrder(order.id)}
                            className="btn btn-sm btn-danger"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="p-4 border-t border-[var(--border)] bg-[var(--bg-secondary)]/30">
              <button
                type="button"
                onClick={() => { setShowOrdersListModal(false); setShowOrderModal(true); }}
                className="btn btn-primary w-full"
              >
                ➕ Добавить заказ
              </button>
            </div>
      </Modal>

      {/* Merge Modal */}
      <Modal isOpen={showMergeModal} onClose={() => setShowMergeModal(false)} contentClassName="w-full max-w-lg p-6 animate-fadeIn">
            <h3 className="text-lg font-semibold mb-4">🔗 Объединить аккаунты</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              Выберите аккаунты для объединения с {client.first_name}. Все сообщения и заказы будут перенесены.
            </p>
            
            <div className="mb-4">
              <input
                type="text"
                value={mergeSearch}
                onChange={e => setMergeSearch(e.target.value)}
                placeholder="Поиск клиентов..."
                className="input"
              />
            </div>

            {mergeResults.length > 0 && (
              <div className="max-h-60 overflow-y-auto space-y-2 mb-4">
                {mergeResults.map(c => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      if (selectedMergeClients.includes(c.id)) {
                        setSelectedMergeClients(prev => prev.filter(id => id !== c.id));
                      } else {
                        setSelectedMergeClients(prev => [...prev, c.id]);
                      }
                    }}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                      selectedMergeClients.includes(c.id)
                        ? 'border-[var(--accent)] bg-[var(--accent)]/20'
                        : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'
                    }`}
                  >
                    <div className="avatar avatar-sm">{c.first_name[0]}</div>
                    <div className="flex-1 text-left">
                      <div className="font-medium">{c.first_name} {c.last_name || ''}</div>
                      <div className="text-xs text-[var(--text-muted)]">
                        {c.username ? `@${c.username}` : `ID: ${c.telegram_user_id}`}
                      </div>
                    </div>
                    {selectedMergeClients.includes(c.id) && (
                      <span className="text-[var(--accent)]">✓</span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {selectedMergeClients.length > 0 && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 mb-4">
                <div className="flex items-center gap-2 text-amber-400 text-sm">
                  <span>⚠️</span>
                  <span>Выбрано {selectedMergeClients.length} аккаунт(ов) для объединения</span>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleMerge}
                disabled={selectedMergeClients.length === 0 || merging}
                className="btn btn-primary flex-1"
              >
                {merging ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  '🔗 Объединить'
                )}
              </button>
              <button type="button" onClick={() => setShowMergeModal(false)} className="btn btn-secondary">
                Отмена
              </button>
            </div>
      </Modal>
      </div>
    </PageWrapper>
  );
}
