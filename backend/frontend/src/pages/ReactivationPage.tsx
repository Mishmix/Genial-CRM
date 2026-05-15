import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getReactivationCandidates, markReactivationAttempt, ReactivationCandidate } from '../api';
import PageWrapper from '../components/PageWrapper';

const CATEGORY_FILTERS: { value: string; label: string; icon: string }[] = [
  { value: 'all', label: 'Все', icon: '🌐' },
  { value: 'too_expensive', label: 'Дорого', icon: '💸' },
  { value: 'no_urgency', label: 'Не сейчас', icon: '⏳' },
  { value: 'chose_competitor', label: 'Выбрал другого', icon: '🥈' },
  { value: 'ghosting', label: 'Пропал', icon: '👻' },
  { value: 'value_unclear', label: 'Не понял ценности', icon: '❓' },
  { value: 'no_budget', label: 'Нет бюджета', icon: '🪫' },
  { value: 'scope_mismatch', label: 'Не подходит', icon: '🧩' },
  { value: 'timing_mismatch', label: 'Занят', icon: '🗓' },
];

type Sort = 'avg_check' | 'days';

export default function ReactivationPage() {
  const [items, setItems] = useState<ReactivationCandidate[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [sort, setSort] = useState<Sort>('avg_check');
  const [marking, setMarking] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getReactivationCandidates();
      setItems(data || []);
    } catch (err) {
      console.error('reactivation load failed:', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      alert('Скопировано — вставь в чат и жми Send');
    } catch {
      alert('Не удалось скопировать — выдели вручную');
    }
  };

  const handleMark = async (conversationId: number) => {
    if (!confirm('Пометить попытку реактивации? Counter +1, last_attempt = сейчас.')) return;
    setMarking(conversationId);
    try {
      await markReactivationAttempt(conversationId);
      await load();
    } catch (err: any) {
      alert(err?.message || 'Не удалось');
    } finally {
      setMarking(null);
    }
  };

  const filtered = (items || [])
    .filter(it => filter === 'all' ? true : it.normalized_category === filter)
    .sort((a, b) => sort === 'avg_check'
      ? (b.avg_check || 0) - (a.avg_check || 0)
      : b.days_since_rejection - a.days_since_rejection);

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-5xl">
        <div className="mb-8 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-2xl shadow-lg shadow-violet-500/30">🔄</div>
          <div>
            <h1 className="text-3xl font-bold"><span className="gradient-text">Реактивация</span></h1>
            <p className="text-[var(--text-secondary)]">Старые отказы, готовые к новой попытке</p>
          </div>
        </div>

        {/* Filters */}
        <div className="card p-4 mb-6 flex flex-wrap items-center gap-2">
          {CATEGORY_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`btn btn-sm ${filter === f.value ? 'btn-primary' : 'btn-ghost'}`}
            >
              {f.icon} {f.label}
              {filter === f.value && items && (
                <span className="ml-1 opacity-70">({(items || []).filter(it => f.value === 'all' || it.normalized_category === f.value).length})</span>
              )}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <label className="text-sm text-[var(--text-muted)]">Сортировать:</label>
            <select className="input input-sm" value={sort} onChange={e => setSort(e.target.value as Sort)}>
              <option value="avg_check">по среднему чеку</option>
              <option value="days">по давности отказа</option>
            </select>
          </div>
        </div>

        {/* List */}
        {filtered.length === 0 ? (
          <div className="card p-8 text-center text-[var(--text-muted)]">
            {items === null ? 'Загрузка…' : 'Нет кандидатов под выбранный фильтр.'}
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(it => (
              <div key={it.conversation_id} className="card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {it.deep_link
                        ? <a href={it.deep_link} className="font-semibold text-lg hover:underline">{it.client_name}</a>
                        : <span className="font-semibold text-lg">{it.client_name}</span>}
                      <span className="badge badge-qualified">{it.category_label}</span>
                      {it.avg_check && <span className="text-xs text-emerald-400">~${it.avg_check.toFixed(0)} ср. чек</span>}
                    </div>
                    <div className="text-sm text-[var(--text-muted)] mb-2">
                      Отказ {it.days_since_rejection} дн. назад · попыток: {it.reactivation_attempts}
                      {it.last_attempt_at && <> · последняя {new Date(it.last_attempt_at).toLocaleDateString('ru-RU')}</>}
                    </div>
                    {it.raw_reason_excerpt && (
                      <div className="text-sm text-[var(--text-secondary)] italic mb-3">
                        «{it.raw_reason_excerpt}»
                      </div>
                    )}
                    <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-sm">
                      {it.suggested_template_preview || <span className="text-[var(--text-muted)]">— шаблон не настроен —</span>}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 min-w-[140px]">
                    {it.deep_link && (
                      <a href={it.deep_link} className="btn btn-ghost btn-sm">💬 Открыть чат</a>
                    )}
                    <button
                      onClick={() => handleCopy(it.suggested_template_preview)}
                      disabled={!it.suggested_template_preview}
                      className="btn btn-ghost btn-sm"
                    >
                      📋 Скопировать
                    </button>
                    <button
                      onClick={() => handleMark(it.conversation_id)}
                      disabled={marking === it.conversation_id}
                      className="btn btn-primary btn-sm"
                    >
                      {marking === it.conversation_id ? '…' : '✓ Отправил'}
                    </button>
                    <Link to={`/clients/${it.client_id}`} className="text-xs text-center text-[var(--text-muted)] hover:underline">
                      Карточка →
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
