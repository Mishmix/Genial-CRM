import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getClients, searchClients, createManualClient, fetchClientAvatar, getClientsStats, Client } from '../api';
import PageWrapper from '../components/PageWrapper';
import { useWebSocket } from '../hooks/useWebSocket';
import Select from '../components/Select';
import { useToast } from '../contexts/ToastContext';

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы', icon: '📊' },
  { value: 'new', label: 'Новый', icon: '✨' },
  { value: 'sent_price', label: 'Прайс', icon: '💰' },
  { value: 'ordered', label: 'Заказал', icon: '✅' },
  { value: 'rejected', label: 'Отказ', icon: '❌' },
];

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [unreadFilter, setUnreadFilter] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(50);
  const [stats, setStats] = useState({ total: 0, new: 0, sent_price: 0, ordered: 0, rejected: 0, unread: 0 });
  const [, forceUpdate] = useState(0);
  const navigate = useNavigate();
  const clientsRef = useRef<Client[]>([]);
  clientsRef.current = clients;
  const toast = useToast();

  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState({
    first_name: '', last_name: '', username: '',
    source: 'whatsapp' as 'whatsapp' | 'instagram' | 'telegram' | 'other',
    phone: '', notes: '',
  });
  const [adding, setAdding] = useState(false);
  const [fetchingAvatars, setFetchingAvatars] = useState(false);

  useWebSocket('new_message', (data: any) => {
    const currentClients = clientsRef.current;
    const idx = currentClients.findIndex(c => c.id === data.client_id);
    let newClients: Client[];
    if (idx >= 0) {
      newClients = [...currentClients];
      newClients[idx] = { ...newClients[idx], unread_count: data.client.unread_count, last_message_at: data.message.sent_at, avatar_local_path: data.client.avatar_local_path || newClients[idx].avatar_local_path, message_count: (newClients[idx].message_count || 0) + (data.message.direction === 'in' ? 1 : 0) };
      const [client] = newClients.splice(idx, 1);
      newClients = [client, ...newClients];
    } else {
      newClients = [{ id: data.client.id, telegram_user_id: data.client.telegram_user_id || 0, username: data.client.username, first_name: data.client.first_name, last_name: data.client.last_name || null, status: data.client.status, unread_count: data.client.unread_count, last_message_at: data.message.sent_at, avatar_local_path: data.client.avatar_local_path || null, tags: data.client.tags || [], is_archived: false, deadline: null, lost_reason: null, first_seen_at: data.client.first_seen_at || new Date().toISOString(), message_count: 1 }, ...currentClients];
      setTotal(t => t + 1);
    }
    setClients(newClients);
    forceUpdate(n => n + 1);
  });

  useWebSocket('client_updated', (data: any) => {
    setClients(clientsRef.current.map(c => c.id === data.client.id ? { ...c, ...data.client } : c));
    forceUpdate(n => n + 1);
  });

  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      // Загружаем статистику
      const statsData = await getClientsStats();
      setStats(statsData);
      
      if (search.trim()) {
        const result = await searchClients(search);
        setClients(result.items); setTotal(result.items.length);
      } else {
        const result = await getClients({ page, per_page: perPage, status: statusFilter || undefined, has_unread: unreadFilter || undefined, include_archived: showArchived || undefined });
        setClients(result.items); setTotal(result.total);
      }
    } catch (err) { console.error('Failed:', err); }
    finally { setLoading(false); }
  }, [search, statusFilter, unreadFilter, showArchived, page, perPage]);

  useEffect(() => { setPage(1); }, [statusFilter, unreadFilter, showArchived]);
  useEffect(() => { loadClients(); }, [loadClients]);
  useEffect(() => { const t = setTimeout(() => { setPage(1); loadClients(); }, 300); return () => clearTimeout(t); }, [search]);

  const totalPages = Math.ceil(total / perPage);

  const handleAddClient = async () => {
    if (!addForm.first_name.trim()) return;
    setAdding(true);
    try {
      const c = await createManualClient({ first_name: addForm.first_name.trim(), last_name: addForm.last_name.trim() || undefined, username: addForm.username.trim() || undefined, source: addForm.source, phone: addForm.phone.trim() || undefined, notes: addForm.notes.trim() || undefined });
      setShowAddModal(false);
      setAddForm({ first_name: '', last_name: '', username: '', source: 'whatsapp', phone: '', notes: '' });
      toast.success(`Клиент ${c.first_name} создан`, '👤');
      navigate(`/clients/${c.id}`);
    } catch (err) { toast.error('Ошибка создания клиента'); }
    finally { setAdding(false); }
  };

  const handleFetchAvatars = async () => {
    setFetchingAvatars(true);
    let count = 0;
    for (const client of clients) {
      if (!client.avatar_local_path && client.telegram_user_id > 0) {
        try {
          const r = await fetchClientAvatar(client.id);
          if (r.success && r.avatar_url) {
            setClients(p => p.map(c => c.id === client.id ? { ...c, avatar_local_path: r.avatar_url! } : c));
            count++;
          }
        } catch {}
        await new Promise(r => setTimeout(r, 200));
      }
    }
    setFetchingAvatars(false);
    if (count > 0) toast.success(`Загружено ${count} аватаров`, '📷');
    else toast.info('Нет новых аватаров для загрузки');
  };

  const formatDate = (d: string | null) => {
    if (!d) return '—';
    const date = new Date(d), now = new Date(), diff = now.getTime() - date.getTime();
    if (diff < 60000) return 'сейчас';
    if (diff < 3600000) return Math.floor(diff / 60000) + ' мин';
    if (diff < 86400000) return Math.floor(diff / 3600000) + ' ч';
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  const getInitials = (n: string) => n.split(' ').map(x => x[0]).join('').toUpperCase().slice(0, 2);

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-6xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-2xl shadow-lg">👥</div>
            <div><h1 className="text-3xl font-bold gradient-text">Клиенты</h1><p className="text-[var(--text-secondary)]">База контактов</p></div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowAddModal(true)} className="btn btn-primary">➕ Добавить</button>
            <button onClick={handleFetchAvatars} disabled={fetchingAvatars} className="btn btn-secondary">{fetchingAvatars ? '...' : '📷'}</button>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-5 mb-8">
          {[{ l: 'Всего', v: stats.total, i: '👥', g: 'from-violet-500/25 to-purple-500/15', b: 'from-violet-500 to-purple-600' },
            { l: 'Новые', v: stats.new, i: '✨', g: 'from-blue-500/25 to-cyan-500/15', b: 'from-blue-500 to-cyan-500' },
            { l: 'Непрочитанные', v: stats.unread, i: '💬', g: 'from-orange-500/25 to-amber-500/15', b: 'from-orange-500 to-amber-500' },
            { l: 'Заказы', v: stats.ordered, i: '✅', g: 'from-emerald-500/25 to-green-500/15', b: 'from-emerald-500 to-green-500' }
          ].map(s => (
            <div key={s.l} className="card stat-card p-5"><div className={'absolute inset-0 bg-gradient-to-br ' + s.g + ' rounded-[20px] opacity-60'} /><div className="flex items-center justify-between relative z-10"><div><p className="text-[var(--text-muted)] text-sm mb-1">{s.l}</p><p className="text-4xl font-bold text-white">{s.v}</p></div><div className={'w-14 h-14 rounded-2xl bg-gradient-to-br ' + s.b + ' flex items-center justify-center text-2xl shadow-lg'}>{s.i}</div></div></div>
          ))}
        </div>

        <div className="card p-5 mb-6">
          <div className="flex gap-3 items-center">
            <div className="relative flex-1">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">🔍</span>
              <input type="text" placeholder="Поиск по имени, username или ID..." value={search} onChange={e => setSearch(e.target.value)} className="input w-full" style={{ paddingLeft: '48px' }} />
            </div>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="input" style={{ width: '180px' }}>
              {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.icon} {o.label}</option>)}
            </select>
            <button onClick={() => setUnreadFilter(!unreadFilter)} className={'btn px-4 ' + (unreadFilter ? 'btn-primary' : 'btn-secondary')}>💬 Непрочитанные</button>
            <button onClick={() => setShowArchived(!showArchived)} className={'btn px-3 ' + (showArchived ? 'btn-primary' : 'btn-secondary')}>📦</button>
          </div>
        </div>

        {loading ? <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="card p-5"><div className="flex gap-4"><div className="skeleton w-12 h-12 rounded-2xl" /><div className="flex-1"><div className="skeleton h-5 w-40 mb-2" /><div className="skeleton h-4 w-24" /></div></div></div>)}</div>
        : clients.length === 0 ? <div className="card py-20 text-center"><div className="text-5xl mb-4">{search ? '🔍' : '👥'}</div><p className="text-xl font-bold mb-2">{search ? 'Ничего не найдено' : 'Нет клиентов'}</p></div>
        : <div className="space-y-4">{clients.map(client => (
            <div key={client.id} onClick={() => navigate('/clients/' + client.id)} className="card card-hover p-5 cursor-pointer">
              <div className="flex items-center gap-5">
                {client.avatar_local_path ? (
                  <img src={'http://localhost:8000' + client.avatar_local_path} alt="" className="w-12 h-12 rounded-2xl object-cover" />
                ) : (
                  <div className="avatar avatar-md">{getInitials(client.first_name)}</div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1"><span className="font-semibold text-lg text-white truncate">{client.first_name} {client.last_name || ''}</span>{client.unread_count > 0 && <span className="unread-badge">{client.unread_count}</span>}</div>
                  <span className="text-sm text-[var(--text-muted)]">{client.username ? '@' + client.username : 'ID: ' + client.telegram_user_id}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className={'badge badge-' + client.status}>{STATUS_OPTIONS.find(s => s.value === client.status)?.icon} {client.status}</span>
                  <span className="text-sm text-[var(--text-muted)] w-16 text-right">{formatDate(client.last_message_at)}</span>
                  <span className="text-[var(--text-muted)]">→</span>
                </div>
              </div>
            </div>
          ))}</div>}

        {/* Pagination */}
        {!search && totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn btn-secondary px-3">←</button>
            {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 7) pageNum = i + 1;
              else if (page <= 4) pageNum = i + 1;
              else if (page >= totalPages - 3) pageNum = totalPages - 6 + i;
              else pageNum = page - 3 + i;
              return <button key={pageNum} onClick={() => setPage(pageNum)} className={`btn px-3 min-w-[40px] ${page === pageNum ? 'btn-primary' : 'btn-secondary'}`}>{pageNum}</button>;
            })}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn btn-secondary px-3">→</button>
            <span className="text-sm text-[var(--text-muted)] ml-4">{((page - 1) * perPage) + 1}–{Math.min(page * perPage, total)} из {total}</span>
          </div>
        )}

        {showAddModal && <div className="modal-overlay" onClick={() => setShowAddModal(false)}><div className="modal-content w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
          <h3 className="text-lg font-semibold mb-4">➕ Добавить клиента</h3>
          <div className="space-y-4">
            <div><label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Источник</label><Select value={addForm.source} onChange={v => setAddForm(f => ({ ...f, source: v as any }))} options={[{ value: 'whatsapp', label: 'WhatsApp', icon: '💬' }, { value: 'instagram', label: 'Instagram', icon: '📸' }, { value: 'telegram', label: 'Telegram', icon: '✈️' }, { value: 'other', label: 'Другое', icon: '📱' }]} /></div>
            <div className="grid grid-cols-2 gap-4"><div><label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Имя *</label><input value={addForm.first_name} onChange={e => setAddForm(f => ({ ...f, first_name: e.target.value }))} className="input" /></div><div><label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Фамилия</label><input value={addForm.last_name} onChange={e => setAddForm(f => ({ ...f, last_name: e.target.value }))} className="input" /></div></div>
            <div className="grid grid-cols-2 gap-4"><div><label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Username</label><input value={addForm.username} onChange={e => setAddForm(f => ({ ...f, username: e.target.value }))} className="input" /></div><div><label className="text-xs font-semibold text-[var(--text-muted)] uppercase mb-2 block">Телефон</label><input value={addForm.phone} onChange={e => setAddForm(f => ({ ...f, phone: e.target.value }))} className="input" /></div></div>
          </div>
          <div className="flex gap-2 mt-6"><button onClick={handleAddClient} disabled={!addForm.first_name.trim() || adding} className="btn btn-primary flex-1">{adding ? '...' : '✅ Создать'}</button><button onClick={() => setShowAddModal(false)} className="btn btn-secondary">Отмена</button></div>
        </div></div>}
      </div>
    </PageWrapper>
  );
}
