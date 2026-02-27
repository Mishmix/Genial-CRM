import { useState, useEffect } from 'react';
import { getTemplates, createTemplate, updateTemplate, deleteTemplate, Template } from '../api';
import PageWrapper from '../components/PageWrapper';
import Modal from '../components/Modal';
import { useToast } from '../contexts/ToastContext';

const LANGUAGES = [
  { code: 'en', name: 'Английский', flag: '🇬🇧' },
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
  { code: 'ua', name: 'Украинский', flag: '🇺🇦' },
  { code: 'es', name: 'Испанский', flag: '🇪🇸' },
];

interface TemplateForm {
  name: string;
  language: string;
  content: string;
  is_auto_reply: boolean;
  is_active: boolean;
}

const emptyForm: TemplateForm = { name: '', language: 'en', content: '', is_auto_reply: false, is_active: true };

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'auto' | 'quick'>('all');
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [form, setForm] = useState<TemplateForm>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const toast = useToast();

  useEffect(() => { loadTemplates(); }, []);

  const loadTemplates = async () => {
    setLoading(true);
    try { const result = await getTemplates(); setTemplates(result.items); }
    catch (err) { console.error('Failed to load templates:', err); }
    finally { setLoading(false); }
  };

  const filteredTemplates = templates.filter(t => {
    if (filter === 'auto') return t.is_auto_reply;
    if (filter === 'quick') return !t.is_auto_reply;
    return true;
  });

  const openEditor = (template?: Template) => {
    if (template) {
      setEditingTemplate(template);
      setForm({ name: template.name, language: template.language, content: template.content, is_auto_reply: template.is_auto_reply, is_active: template.is_active });
    } else {
      setEditingTemplate(null);
      setForm(emptyForm);
    }
    setError('');
    setIsEditorOpen(true);
  };

  const closeEditor = () => { setIsEditorOpen(false); setEditingTemplate(null); setForm(emptyForm); setError(''); };

  const handleSave = async () => {
    if (!form.name.trim() || !form.content.trim()) { setError('Название и содержимое обязательны'); return; }
    setSaving(true);
    setError('');
    try {
      if (editingTemplate) {
        const updated = await updateTemplate(editingTemplate.id, form);
        setTemplates(templates.map(t => t.id === updated.id ? updated : t));
        toast.success('Шаблон обновлён', '📝');
      } else {
        const created = await createTemplate(form);
        setTemplates([...templates, created]);
        toast.success('Шаблон создан', '✨');
      }
      closeEditor();
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to save'); toast.error('Ошибка сохранения'); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!editingTemplate || !confirm('Вы уверены, что хотите удалить этот шаблон?')) return;
    setDeleting(true);
    try {
      await deleteTemplate(editingTemplate.id);
      setTemplates(templates.filter(t => t.id !== editingTemplate.id));
      closeEditor();
      toast.success('Шаблон удалён', '🗑️');
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed to delete'); toast.error('Ошибка удаления'); }
    finally { setDeleting(false); }
  };

  const handleToggleActive = async (template: Template) => {
    try {
      const updated = await updateTemplate(template.id, { is_active: !template.is_active });
      setTemplates(templates.map(t => t.id === updated.id ? updated : t));
      toast.info(updated.is_active ? 'Шаблон активирован' : 'Шаблон деактивирован');
    }
    catch (err) { toast.error('Ошибка'); }
  };

  const getLangInfo = (code: string) => LANGUAGES.find(l => l.code === code) || { code, name: code, flag: '🌐' };

  const stats = { total: templates.length, auto: templates.filter(t => t.is_auto_reply).length, quick: templates.filter(t => !t.is_auto_reply).length, active: templates.filter(t => t.is_active).length };

  const statCards = [
    { label: 'Всего', value: stats.total, icon: '📝', gradient: 'from-violet-500/20 to-purple-500/10', iconBg: 'from-violet-500 to-purple-600' },
    { label: 'Автоответы', value: stats.auto, icon: '🤖', gradient: 'from-emerald-500/20 to-green-500/10', iconBg: 'from-emerald-500 to-green-500' },
    { label: 'Быстрые', value: stats.quick, icon: '⚡', gradient: 'from-blue-500/20 to-cyan-500/10', iconBg: 'from-blue-500 to-cyan-500' },
    { label: 'Активные', value: stats.active, icon: '✅', gradient: 'from-teal-500/20 to-emerald-500/10', iconBg: 'from-teal-500 to-emerald-500' },
  ];

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-6xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-2xl shadow-lg shadow-blue-500/30">📝</div>
            <div>
              <h1 className="text-3xl font-bold"><span className="gradient-text">Шаблоны</span></h1>
              <p className="text-[var(--text-secondary)]">Управление автоответами и быстрыми ответами</p>
            </div>
          </div>
          <button type="button" onClick={() => openEditor()} className="btn btn-primary btn-lg">
            <span className="text-xl">+</span> Новый шаблон
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-5 mb-8">
          {statCards.map((stat) => (
            <div key={stat.label} className="card stat-card p-5">
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.gradient} rounded-[20px] opacity-50`} />
              <div className="flex items-center justify-between relative z-10">
                <div>
                  <p className="text-[var(--text-muted)] text-sm font-medium mb-1">{stat.label}</p>
                  <p className="text-3xl font-bold">{stat.value}</p>
                </div>
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.iconBg} flex items-center justify-center text-xl shadow-lg`}>{stat.icon}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2 mb-6">
          {[
            { key: 'all', label: 'Все шаблоны', icon: '📋' },
            { key: 'auto', label: 'Автоответы', icon: '🤖' },
            { key: 'quick', label: 'Быстрые ответы', icon: '⚡' },
          ].map(tab => (
            <button key={tab.key} type="button" onClick={() => setFilter(tab.key as typeof filter)} className={`btn ${filter === tab.key ? 'btn-primary' : 'btn-secondary'}`}>
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Templates grid */}
        {loading ? (
          <div className="grid grid-cols-2 gap-5">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="card p-6"><div className="skeleton h-6 w-48 mb-3" /><div className="skeleton h-4 w-32 mb-4" /><div className="skeleton h-28 rounded-xl" /></div>
            ))}
          </div>
        ) : filteredTemplates.length === 0 ? (
          <div className="card card-gradient">
            <div className="empty-state py-20">
              <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-blue-500/20 to-cyan-500/10 flex items-center justify-center text-5xl mb-6 mx-auto">📝</div>
              <div className="empty-state-title text-2xl mb-2">Шаблоны не найдены</div>
              <div className="empty-state-text text-base mb-4">Создайте первый шаблон</div>
              <button type="button" onClick={() => openEditor()} className="btn btn-primary">+ Создать шаблон</button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-5">
            {filteredTemplates.map((template) => {
              const lang = getLangInfo(template.language);
              return (
                <div key={template.id} className="card card-hover p-6 cursor-pointer" onClick={() => openEditor(template)}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-lg mb-2 truncate">{template.name}</h3>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="badge bg-[var(--bg-hover)] text-[var(--text-secondary)] border border-[var(--border)]">{lang.flag} {lang.name}</span>
                        {template.is_auto_reply && <span className="badge badge-qualified">🤖 Авто</span>}
                        {!template.is_active && <span className="badge badge-lost">Неактивен</span>}
                      </div>
                    </div>
                    <button type="button" onClick={(e) => { e.stopPropagation(); handleToggleActive(template); }} className={`toggle ${template.is_active ? 'active' : ''}`} />
                  </div>

                  <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-secondary)] line-clamp-3 whitespace-pre-wrap">
                    {template.content}
                  </div>

                  <div className="mt-4 flex items-center justify-between text-xs text-[var(--text-muted)]">
                    <span>Нажмите для редактирования</span>
                    <span>→</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Editor Modal */}
        <Modal isOpen={isEditorOpen} onClose={closeEditor} contentClassName="w-full max-w-2xl max-h-[90vh] overflow-hidden">
          {/* Header */}
          <div className="p-6 border-b border-[var(--border)] flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-xl shadow-lg shadow-violet-500/30">
                {editingTemplate ? '✏️' : '✨'}
              </div>
              <div>
                <h2 className="text-xl font-bold gradient-text">{editingTemplate ? 'Редактировать шаблон' : 'Новый шаблон'}</h2>
                <p className="text-sm text-[var(--text-muted)]">{editingTemplate ? 'Изменить шаблон' : 'Создать новый шаблон сообщения'}</p>
              </div>
            </div>
            <button type="button" onClick={closeEditor} className="btn btn-icon btn-ghost text-xl">✕</button>
          </div>

          {/* Form */}
          <div className="p-6 space-y-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 200px)' }}>
            {error && <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-3"><span className="text-xl">⚠️</span> {error}</div>}

            <div>
              <label className="block text-sm font-semibold mb-2">Название шаблона</label>
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="например, Приветствие" />
            </div>

            <div>
              <label className="block text-sm font-semibold mb-2">Язык</label>
              <div className="flex gap-2 flex-wrap">
                {LANGUAGES.map(lang => (
                  <button key={lang.code} type="button" onClick={() => setForm({ ...form, language: lang.code })} className={`btn btn-sm ${form.language === lang.code ? 'btn-primary' : 'btn-secondary'}`}>
                    {lang.flag} {lang.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold mb-2">Содержимое</label>
              <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} className="input" rows={6} placeholder="Напишите текст шаблона..." />
              <p className="text-xs text-[var(--text-muted)] mt-2 flex items-center gap-2">
                <span className="text-base">💡</span> Переменные: <code className="px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--accent)]">{'{first_name}'}</code>, <code className="px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--accent)]">{'{username}'}</code>, <code className="px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--accent)]">{'{portfolio_url}'}</code>
              </p>
            </div>

            <div className="flex gap-6">
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={form.is_auto_reply} onChange={(e) => setForm({ ...form, is_auto_reply: e.target.checked })} className="w-5 h-5 rounded border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--accent)] focus:ring-[var(--accent)]" />
                <div>
                  <div className="font-medium">Автоответ</div>
                  <div className="text-xs text-[var(--text-muted)]">Отправлять автоматически на новые сообщения</div>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="w-5 h-5 rounded border-[var(--border)] bg-[var(--bg-secondary)] text-[var(--accent)] focus:ring-[var(--accent)]" />
                <div>
                  <div className="font-medium">Активен</div>
                  <div className="text-xs text-[var(--text-muted)]">Шаблон доступен для использования</div>
                </div>
              </label>
            </div>
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-[var(--border)] flex items-center justify-between bg-[var(--bg-secondary)]/30 flex-shrink-0">
            <div>
              {editingTemplate && (
                <button type="button" onClick={handleDelete} disabled={deleting} className="btn btn-danger">{deleting ? 'Удаление...' : '🗑️ Удалить'}</button>
              )}
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={closeEditor} className="btn btn-secondary">Отмена</button>
              <button type="button" onClick={handleSave} disabled={saving} className="btn btn-primary">
                {saving ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />Сохранение...</> : editingTemplate ? '✓ Сохранить' : '✨ Создать шаблон'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </PageWrapper>
  );
}
