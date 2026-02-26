import { useState, useEffect, useRef } from 'react';
import { getSettings, updateSetting, getTodoistConfig, updateTodoistConfig, testTodoistConnection, getTodoistProjects, getTodoistSections, TodoistProject, importTelegramExport, getBackups, getBackupStats, createBackup, deleteBackup, restoreBackup, cleanupBackups, getBackupDownloadUrl, Backup, BackupStats } from '../api';
import PageWrapper from '../components/PageWrapper';
import { useToast } from '../contexts/ToastContext';

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    // Bot configuration
    telegram_bot_token: '',
    telegram_bot_token_set: false,
    llm_provider: 'groq',
    groq_api_key: '',
    groq_api_key_set: false,
    nim_api_key: '',
    nim_api_key_set: false,
    mini_app_url: '',
    admin_telegram_ids: '',
    // App settings
    portfolio_url: '',
    auto_reply_enabled: true,
  });
  const [todoistConfig, setTodoistConfig] = useState({
    api_token_masked: '',
    api_token_set: false,
    project_id: '',
    section_today_id: '',
    section_not_today_id: '',
    enabled: false,
  });
  const [todoistProjects, setTodoistProjects] = useState<TodoistProject[]>([]);
  const [todoistSections, setTodoistSections] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [showTokens, setShowTokens] = useState<Record<string, boolean>>({});
  const [newValues, setNewValues] = useState<Record<string, string>>({});
  const [todoistTesting, setTodoistTesting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{clients: number; messages: number; skipped: number} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  
  // Backup state
  const [backups, setBackups] = useState<Backup[]>([]);
  const [backupStats, setBackupStats] = useState<BackupStats | null>(null);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupCreating, setBackupCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [confirmRestore, setConfirmRestore] = useState<string | null>(null);

  useEffect(() => { loadSettings(); loadBackups(); }, []);

  const loadSettings = async () => {
    setLoading(true);
    try { 
      const [data, todoist] = await Promise.all([
        getSettings(),
        getTodoistConfig().catch(() => null)
      ]);
      setSettings(s => ({ ...s, ...data })); 
      if (todoist) {
        setTodoistConfig(todoist);
        // Загружаем проекты если токен настроен
        if (todoist.api_token_set) {
          loadTodoistProjects();
          if (todoist.project_id) {
            loadTodoistSections(todoist.project_id);
          }
        }
      }
    }
    catch (err) { console.error('Failed to load settings:', err); }
    finally { setLoading(false); }
  };

  const loadTodoistProjects = async () => {
    try {
      const data = await getTodoistProjects();
      setTodoistProjects(data.items);
    } catch (err) {
      console.error('Failed to load Todoist projects:', err);
    }
  };

  const loadTodoistSections = async (projectId: string) => {
    try {
      const data = await getTodoistSections(projectId);
      setTodoistSections(data.items);
    } catch (err) {
      console.error('Failed to load Todoist sections:', err);
    }
  };

  const handleTodoistTest = async () => {
    setTodoistTesting(true);
    try {
      await testTodoistConnection();
      toast.success('Подключение к Todoist успешно!', '✅');
      loadTodoistProjects();
    } catch (err) {
      toast.error('Не удалось подключиться к Todoist');
    } finally {
      setTodoistTesting(false);
    }
  };

  const handleTodoistSave = async (key: string, value: string | boolean) => {
    setSaving(`todoist_${key}`);
    try {
      await updateTodoistConfig({ [key]: value });
      toast.success('Настройка сохранена', '✅');
      
      // Обновляем локальное состояние
      if (key === 'api_token') {
        setTodoistConfig(c => ({ ...c, api_token_set: true, api_token_masked: String(value).slice(0, 4) + '...' + String(value).slice(-4) }));
        setNewValues(prev => ({ ...prev, todoist_api_token: '' }));
        loadTodoistProjects();
      } else if (key === 'project_id') {
        setTodoistConfig(c => ({ ...c, project_id: String(value) }));
        loadTodoistSections(String(value));
      } else if (key === 'section_today_id') {
        setTodoistConfig(c => ({ ...c, section_today_id: String(value) }));
      } else if (key === 'section_not_today_id') {
        setTodoistConfig(c => ({ ...c, section_not_today_id: String(value) }));
      } else if (key === 'enabled') {
        setTodoistConfig(c => ({ ...c, enabled: Boolean(value) }));
      }
    } catch (err) {
      toast.error('Ошибка сохранения');
    } finally {
      setSaving(null);
    }
  };

  const handleSave = async (key: string, value: string) => {
    setSaving(key);
    setSaved(null);
    try { 
      await updateSetting(key, value); 
      setSaved(key); 
      // Reload settings to get updated masked values
      await loadSettings();
      // Clear the input field for sensitive data
      setNewValues(prev => ({ ...prev, [key]: '' }));
      toast.success('Настройка сохранена', '✅');
      setTimeout(() => setSaved(null), 2000); 
    }
    catch (err) { toast.error('Ошибка сохранения'); }
    finally { setSaving(null); }
  };

  const handleToggle = async (key: string, value: boolean) => {
    setSettings(s => ({ ...s, [key]: value }));
    await handleSave(key, String(value));
  };

  const toggleShow = (key: string) => {
    setShowTokens(prev => ({ ...prev, [key]: !prev[key] }));
  };
  
  // Backup functions
  const loadBackups = async () => {
    setBackupLoading(true);
    try {
      const [backupsData, statsData] = await Promise.all([
        getBackups(),
        getBackupStats(),
      ]);
      setBackups(backupsData.backups);
      setBackupStats(statsData);
    } catch (err) {
      console.error('Failed to load backups:', err);
    } finally {
      setBackupLoading(false);
    }
  };
  
  const handleCreateBackup = async () => {
    setBackupCreating(true);
    try {
      await createBackup('manual', true);
      toast.success('Бекап создан', '✅');
      loadBackups();
    } catch (err) {
      toast.error('Ошибка создания бекапа');
    } finally {
      setBackupCreating(false);
    }
  };
  
  const handleDeleteBackup = async (filename: string) => {
    try {
      await deleteBackup(filename);
      toast.success('Бекап удалён', '🗑️');
      loadBackups();
    } catch (err) {
      toast.error('Ошибка удаления');
    }
  };
  
  const handleRestoreBackup = async (filename: string) => {
    setRestoring(filename);
    try {
      await restoreBackup(filename);
      toast.success('База данных восстановлена! Перезагрузите страницу.', '✅');
      setConfirmRestore(null);
    } catch (err) {
      toast.error('Ошибка восстановления');
    } finally {
      setRestoring(null);
    }
  };
  
  const handleCleanup = async () => {
    try {
      const result = await cleanupBackups();
      toast.success(`Удалено ${result.deleted} старых бекапов`, '🧹');
      loadBackups();
    } catch (err) {
      toast.error('Ошибка очистки');
    }
  };
  
  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('ru-RU', { 
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };
  
  const getBackupTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      daily: '📅 Ежедневный',
      weekly: '📆 Еженедельный',
      monthly: '🗓️ Ежемесячный',
      manual: '👤 Ручной',
      pre_restore: '⚠️ До восстановления',
    };
    return labels[type] || type;
  };

  if (loading) {
    return (
      <div className="max-w-4xl">
        <div className="mb-8"><div className="skeleton h-8 w-48 mb-2" /><div className="skeleton h-5 w-64" /></div>
        <div className="space-y-6">{[...Array(5)].map((_, i) => <div key={i} className="card p-6"><div className="skeleton h-32" /></div>)}</div>
      </div>
    );
  }

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-4xl">
      {/* Header */}
      <div className="mb-8 stagger-item">
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center text-2xl shadow-lg shadow-orange-500/30">⚙️</div>
          <div>
            <h1 className="text-3xl font-bold"><span className="gradient-text">Настройки</span></h1>
            <p className="text-[var(--text-secondary)]">Конфигурация CRM бота</p>
          </div>
        </div>
      </div>

      {/* Status Banner */}
      <div className="card p-5 mb-6 stagger-item">
        <div className="flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${settings.telegram_bot_token_set ? 'bg-emerald-500' : 'bg-red-500'}`} />
            <span className="text-sm text-[var(--text-secondary)]">Токен бота</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${settings.llm_provider === 'nim' ? (settings.nim_api_key_set ? 'bg-emerald-500' : 'bg-red-500') : (settings.groq_api_key_set ? 'bg-emerald-500' : 'bg-red-500')}`} />
            <span className="text-sm text-[var(--text-secondary)]">Нейросеть ({settings.llm_provider === 'nim' ? 'NIM' : 'Groq'})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${settings.mini_app_url ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-sm text-[var(--text-secondary)]">Mini App</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${settings.admin_telegram_ids ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-sm text-[var(--text-secondary)]">ID админа</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${todoistConfig.enabled ? 'bg-emerald-500' : 'bg-gray-500'}`} />
            <span className="text-sm text-[var(--text-secondary)]">Todoist</span>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        
        {/* === TELEGRAM BOT TOKEN === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 to-cyan-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(59, 130, 246, 0.5)' }}>🤖</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Токен Telegram бота</h3>
                <p className="text-sm text-[var(--text-secondary)]">
                  Получить у <a href="https://t.me/BotFather" target="_blank" rel="noopener" className="text-[var(--accent)] hover:underline">@BotFather</a>
                </p>
              </div>
              {settings.telegram_bot_token_set && (
                <span className="badge badge-qualified">✓ Настроено</span>
              )}
            </div>
            
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <input 
                  type={showTokens['telegram_bot_token'] ? 'text' : 'password'} 
                  value={newValues['telegram_bot_token'] || ''} 
                  onChange={(e) => setNewValues(prev => ({ ...prev, telegram_bot_token: e.target.value }))} 
                  className="input pr-12 font-mono text-sm" 
                  placeholder={settings.telegram_bot_token_set ? `Current: ${settings.telegram_bot_token}` : "Enter bot token..."} 
                />
                <button onClick={() => toggleShow('telegram_bot_token')} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                  {showTokens['telegram_bot_token'] ? '🙈' : '👁️'}
                </button>
              </div>
              <button 
                onClick={() => handleSave('telegram_bot_token', newValues['telegram_bot_token'] || '')} 
                disabled={saving === 'telegram_bot_token' || !newValues['telegram_bot_token']} 
                className="btn btn-primary min-w-[110px]"
              >
                {saving === 'telegram_bot_token' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : saved === 'telegram_bot_token' ? '✓ Сохранено' : 'Сохранить'}
              </button>
            </div>
            
            <p className="text-xs text-[var(--text-muted)] mt-3">⚠️ После изменения перезапустите бэкенд</p>
          </div>
        </div>

        {/* === LLM PROVIDER === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/20 to-green-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(16, 185, 129, 0.5)' }}>🧠</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Нейросеть (LLM)</h3>
                <p className="text-sm text-[var(--text-secondary)]">
                  Выберите модель для парсинга и анализа чатов
                </p>
              </div>
            </div>

            <div className="flex gap-4 mb-6">
              <label className={`flex-1 flex items-center justify-center gap-2 p-4 rounded-xl border-2 cursor-pointer transition-all ${settings.llm_provider === 'groq' ? 'border-emerald-500 bg-emerald-500/10' : 'border-[var(--border)] hover:border-[var(--text-muted)]'}`}>
                <input 
                  type="radio" 
                  name="llm_provider" 
                  value="groq" 
                  checked={settings.llm_provider === 'groq'}
                  onChange={() => handleSave('llm_provider', 'groq')}
                  className="hidden" 
                />
                <span className="font-semibold text-[var(--text-primary)]">Groq</span>
              </label>
              
              <label className={`flex-1 flex items-center justify-center gap-2 p-4 rounded-xl border-2 cursor-pointer transition-all ${settings.llm_provider === 'nim' ? 'border-emerald-500 bg-emerald-500/10' : 'border-[var(--border)] hover:border-[var(--text-muted)]'}`}>
                <input 
                  type="radio" 
                  name="llm_provider" 
                  value="nim" 
                  checked={settings.llm_provider === 'nim'}
                  onChange={() => handleSave('llm_provider', 'nim')}
                  className="hidden" 
                />
                <span className="font-semibold text-[var(--text-primary)]">NVIDIA NIM (Kimi) 🌟</span>
              </label>
            </div>

            {settings.llm_provider === 'groq' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="flex items-center gap-2 mb-3">
                  <span className="font-semibold text-[var(--text-primary)]">Groq API ключ</span>
                  {settings.groq_api_key_set && <span className="badge badge-qualified text-xs">✓ Настроено</span>}
                </div>
                <div className="flex gap-3">
                  <div className="flex-1 relative">
                    <input 
                      type={showTokens['groq_api_key'] ? 'text' : 'password'} 
                      value={newValues['groq_api_key'] || ''} 
                      onChange={(e) => setNewValues(prev => ({ ...prev, groq_api_key: e.target.value }))} 
                      className="input pr-12 font-mono text-sm" 
                      placeholder={settings.groq_api_key_set ? `Current: ${settings.groq_api_key}` : "gsk_..."} 
                    />
                    <button onClick={() => toggleShow('groq_api_key')} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                      {showTokens['groq_api_key'] ? '🙈' : '👁️'}
                    </button>
                  </div>
                  <button 
                    onClick={() => handleSave('groq_api_key', newValues['groq_api_key'] || '')} 
                    disabled={saving === 'groq_api_key' || !newValues['groq_api_key']} 
                    className="btn btn-primary min-w-[110px]"
                  >
                    {saving === 'groq_api_key' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : saved === 'groq_api_key' ? '✓ Сохранено' : 'Сохранить'}
                  </button>
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-2">
                  Используется для классификации с GPT-OSS-120B. Получить на <a href="https://console.groq.com" target="_blank" rel="noopener" className="text-[var(--accent)] hover:underline">console.groq.com</a> (бесплатно)
                </p>
              </div>
            )}

            {settings.llm_provider === 'nim' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="flex items-center gap-2 mb-3">
                  <span className="font-semibold text-[var(--text-primary)]">NVIDIA NIM API ключ</span>
                  {settings.nim_api_key_set && <span className="badge badge-qualified text-xs">✓ Настроено</span>}
                </div>
                <div className="flex gap-3">
                  <div className="flex-1 relative">
                    <input 
                      type={showTokens['nim_api_key'] ? 'text' : 'password'} 
                      value={newValues['nim_api_key'] || ''} 
                      onChange={(e) => setNewValues(prev => ({ ...prev, nim_api_key: e.target.value }))} 
                      className="input pr-12 font-mono text-sm" 
                      placeholder={settings.nim_api_key_set ? `Current: ${settings.nim_api_key}` : "nvapi-..."} 
                    />
                    <button onClick={() => toggleShow('nim_api_key')} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                      {showTokens['nim_api_key'] ? '🙈' : '👁️'}
                    </button>
                  </div>
                  <button 
                    onClick={() => handleSave('nim_api_key', newValues['nim_api_key'] || '')} 
                    disabled={saving === 'nim_api_key' || !newValues['nim_api_key']} 
                    className="btn btn-primary min-w-[110px]"
                  >
                    {saving === 'nim_api_key' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : saved === 'nim_api_key' ? '✓ Сохранено' : 'Сохранить'}
                  </button>
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-2">
                  Используется для парсинга заказов с Kimi k2.5. Получить на <a href="https://build.nvidia.com" target="_blank" rel="noopener" className="text-[var(--accent)] hover:underline">build.nvidia.com</a> (бесплатно)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* === MINI APP URL === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-500/20 to-purple-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(139, 92, 246, 0.5)' }}>📱</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">URL Mini App</h3>
                <p className="text-sm text-[var(--text-secondary)]">Ссылка, которая отправляется клиентам</p>
              </div>
              {settings.mini_app_url && (
                <span className="badge badge-qualified">✓ Указан</span>
              )}
            </div>
            
            <div className="flex gap-3">
              <input 
                type="url" 
                value={newValues['mini_app_url'] ?? settings.mini_app_url} 
                onChange={(e) => setNewValues(prev => ({ ...prev, mini_app_url: e.target.value }))} 
                className="input flex-1" 
                placeholder="https://t.me/your_bot/app" 
              />
              <button 
                onClick={() => handleSave('mini_app_url', newValues['mini_app_url'] ?? settings.mini_app_url)} 
                disabled={saving === 'mini_app_url'} 
                className="btn btn-primary min-w-[110px]"
              >
                {saving === 'mini_app_url' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : saved === 'mini_app_url' ? '✓ Сохранено' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>

        {/* === ADMIN TELEGRAM ID === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-amber-500/20 to-orange-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(245, 158, 11, 0.5)' }}>👤</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Ваш Telegram ID</h3>
                <p className="text-sm text-[var(--text-secondary)]">
                  Узнать у <a href="https://t.me/userinfobot" target="_blank" rel="noopener" className="text-[var(--accent)] hover:underline">@userinfobot</a> — нужен для определения ваших ответов
                </p>
              </div>
              {settings.admin_telegram_ids && (
                <span className="badge badge-qualified">✓ Указан</span>
              )}
            </div>
            
            <div className="flex gap-3">
              <input 
                type="text" 
                value={newValues['admin_telegram_ids'] ?? settings.admin_telegram_ids} 
                onChange={(e) => setNewValues(prev => ({ ...prev, admin_telegram_ids: e.target.value }))} 
                className="input flex-1 font-mono" 
                placeholder="123456789" 
              />
              <button 
                onClick={() => handleSave('admin_telegram_ids', newValues['admin_telegram_ids'] ?? settings.admin_telegram_ids)} 
                disabled={saving === 'admin_telegram_ids'} 
                className="btn btn-primary min-w-[110px]"
              >
                {saving === 'admin_telegram_ids' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : saved === 'admin_telegram_ids' ? '✓ Сохранено' : 'Сохранить'}
              </button>
            </div>
            
            <p className="text-xs text-[var(--text-muted)] mt-3">Когда вы отвечаете клиенту, бот перестаёт анализировать этот чат</p>
          </div>
        </div>

        {/* === AUTO-REPLY TOGGLE === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-teal-500/20 to-cyan-500/10 rounded-[20px]" />
          <div className="flex items-center justify-between relative z-10">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-teal-500 to-cyan-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(20, 184, 166, 0.5)' }}>💬</div>
              <div>
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Автоответ</h3>
                <p className="text-sm text-[var(--text-secondary)]">Автоматически классифицировать и отвечать на новые сообщения</p>
              </div>
            </div>
            <button onClick={() => handleToggle('auto_reply_enabled', !settings.auto_reply_enabled)} className={`toggle ${settings.auto_reply_enabled ? 'active' : ''}`} />
          </div>
        </div>

        {/* === PORTFOLIO URL === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-pink-500/20 to-rose-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(236, 72, 153, 0.5)' }}>🔗</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">URL портфолио</h3>
                <p className="text-sm text-[var(--text-secondary)]">Используется в шаблонах как {'{portfolio_url}'}</p>
              </div>
            </div>
            
            <div className="flex gap-3">
              <input 
                type="url" 
                value={newValues['portfolio_url'] ?? settings.portfolio_url} 
                onChange={(e) => setNewValues(prev => ({ ...prev, portfolio_url: e.target.value }))} 
                className="input flex-1" 
                placeholder="https://example.com/portfolio" 
              />
              <button 
                onClick={() => handleSave('portfolio_url', newValues['portfolio_url'] ?? settings.portfolio_url)} 
                disabled={saving === 'portfolio_url'} 
                className="btn btn-primary min-w-[110px]"
              >
                {saving === 'portfolio_url' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : saved === 'portfolio_url' ? '✓ Сохранено' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>

        {/* === TODOIST INTEGRATION === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/20 to-orange-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(239, 68, 68, 0.5)' }}>✅</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Todoist интеграция</h3>
                <p className="text-sm text-[var(--text-secondary)]">
                  Автоматическое создание задач при добавлении заказов
                </p>
              </div>
              <div className="flex items-center gap-3">
                {todoistConfig.api_token_set && (
                  <span className="badge badge-qualified">✓ Подключено</span>
                )}
                <button 
                  onClick={() => handleTodoistSave('enabled', !todoistConfig.enabled)} 
                  className={`toggle ${todoistConfig.enabled ? 'active' : ''}`}
                  disabled={!todoistConfig.api_token_set}
                />
              </div>
            </div>
            
            {/* API Token */}
            <div className="space-y-4">
              <div>
                <label className="text-sm text-[var(--text-secondary)] mb-2 block">API токен</label>
                <div className="flex gap-3">
                  <div className="flex-1 relative">
                    <input 
                      type={showTokens['todoist_api_token'] ? 'text' : 'password'} 
                      value={newValues['todoist_api_token'] || ''} 
                      onChange={(e) => setNewValues(prev => ({ ...prev, todoist_api_token: e.target.value }))} 
                      className="input pr-12 font-mono text-sm" 
                      placeholder={todoistConfig.api_token_set ? `Текущий: ${todoistConfig.api_token_masked}` : "Вставьте API токен..."} 
                    />
                    <button onClick={() => toggleShow('todoist_api_token')} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                      {showTokens['todoist_api_token'] ? '🙈' : '👁️'}
                    </button>
                  </div>
                  <button 
                    onClick={() => handleTodoistSave('api_token', newValues['todoist_api_token'] || '')} 
                    disabled={saving === 'todoist_api_token' || !newValues['todoist_api_token']} 
                    className="btn btn-primary min-w-[110px]"
                  >
                    {saving === 'todoist_api_token' ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Сохранить'}
                  </button>
                  {todoistConfig.api_token_set && (
                    <button 
                      onClick={handleTodoistTest} 
                      disabled={todoistTesting} 
                      className="btn btn-secondary min-w-[100px]"
                    >
                      {todoistTesting ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Тест'}
                    </button>
                  )}
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-2">
                  Получить на <a href="https://app.todoist.com/app/settings/integrations/developer" target="_blank" rel="noopener" className="text-[var(--accent)] hover:underline">todoist.com/settings/integrations/developer</a>
                </p>
              </div>

              {/* Project Selection */}
              {todoistConfig.api_token_set && todoistProjects.length > 0 && (
                <div>
                  <label className="text-sm text-[var(--text-secondary)] mb-2 block">Проект</label>
                  <select 
                    value={todoistConfig.project_id} 
                    onChange={(e) => handleTodoistSave('project_id', e.target.value)}
                    className="input"
                  >
                    <option value="">Выберите проект...</option>
                    {todoistProjects.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Section Selection */}
              {todoistConfig.project_id && Object.keys(todoistSections).length > 0 && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-[var(--text-secondary)] mb-2 block">Секция "Today"</label>
                    <select 
                      value={todoistConfig.section_today_id} 
                      onChange={(e) => handleTodoistSave('section_today_id', e.target.value)}
                      className="input"
                    >
                      <option value="">Выберите секцию...</option>
                      {Object.entries(todoistSections).map(([name, id]) => (
                        <option key={id} value={id}>{name}</option>
                      ))}
                    </select>
                    <p className="text-xs text-[var(--text-muted)] mt-1">Для заказов с дедлайном сегодня</p>
                  </div>
                  <div>
                    <label className="text-sm text-[var(--text-secondary)] mb-2 block">Секция "Not Today"</label>
                    <select 
                      value={todoistConfig.section_not_today_id} 
                      onChange={(e) => handleTodoistSave('section_not_today_id', e.target.value)}
                      className="input"
                    >
                      <option value="">Выберите секцию...</option>
                      {Object.entries(todoistSections).map(([name, id]) => (
                        <option key={id} value={id}>{name}</option>
                      ))}
                    </select>
                    <p className="text-xs text-[var(--text-muted)] mt-1">Для остальных заказов</p>
                  </div>
                </div>
              )}

              {/* Status */}
              {todoistConfig.enabled && todoistConfig.project_id && todoistConfig.section_today_id && todoistConfig.section_not_today_id && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <p className="text-sm text-emerald-400">
                    ✅ Интеграция активна. Новые заказы будут автоматически добавляться в Todoist.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* === TELEGRAM IMPORT === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/20 to-blue-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(6, 182, 212, 0.5)' }}>📥</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Импорт из Telegram</h3>
                <p className="text-sm text-[var(--text-secondary)]">
                  Загрузите историю чатов из Telegram Desktop
                </p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)]">
                <p className="text-sm text-[var(--text-secondary)] mb-3">
                  <strong>Как экспортировать:</strong>
                </p>
                <ol className="text-sm text-[var(--text-muted)] space-y-1 list-decimal list-inside">
                  <li>Откройте Telegram Desktop</li>
                  <li>Настройки → Продвинутые → Экспорт данных</li>
                  <li>Выберите "Личные чаты"</li>
                  <li>Формат: <strong>Машиночитаемый JSON</strong></li>
                  <li>Без медиафайлов (для скорости)</li>
                  <li>Загрузите файл <code>result.json</code></li>
                </ol>
              </div>
              
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  
                  setImporting(true);
                  setImportResult(null);
                  
                  try {
                    const result = await importTelegramExport(file);
                    setImportResult({
                      clients: result.imported_clients,
                      messages: result.imported_messages,
                      skipped: result.skipped_messages,
                    });
                    toast.success(`Импортировано: ${result.imported_clients} клиентов, ${result.imported_messages} сообщений`, '✅');
                  } catch (err: any) {
                    toast.error(err.message || 'Ошибка импорта');
                  } finally {
                    setImporting(false);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }
                }}
              />
              
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importing || !settings.admin_telegram_ids}
                className="btn btn-primary w-full"
              >
                {importing ? (
                  <><div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" /> Импорт...</>
                ) : (
                  '📂 Выбрать файл result.json'
                )}
              </button>
              
              {!settings.admin_telegram_ids && (
                <p className="text-xs text-amber-400">⚠️ Сначала укажите ваш Telegram ID выше</p>
              )}
              
              {importResult && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <p className="text-sm text-emerald-400">
                    ✅ Импорт завершён: {importResult.clients} клиентов, {importResult.messages} сообщений
                    {importResult.skipped > 0 && ` (пропущено ${importResult.skipped} дубликатов)`}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* === DATABASE BACKUPS === */}
        <div className="card p-6 stagger-item">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 to-purple-500/10 rounded-[20px]" />
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-5">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl shadow-lg" style={{ boxShadow: '0 8px 30px -5px rgba(99, 102, 241, 0.5)' }}>💾</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-[var(--text-primary)]">Резервные копии</h3>
                <p className="text-sm text-[var(--text-secondary)]">
                  Автоматические бекапы: ежедневно, еженедельно, ежемесячно
                </p>
              </div>
              {backupStats && (
                <span className="badge badge-qualified">{backupStats.total_count} бекапов</span>
              )}
            </div>
            
            {/* Stats */}
            {backupStats && (
              <div className="grid grid-cols-4 gap-3 mb-5">
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
                  <div className="text-2xl font-bold text-[var(--text-primary)]">{backupStats.by_type.daily?.count || 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Ежедневных</div>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
                  <div className="text-2xl font-bold text-[var(--text-primary)]">{backupStats.by_type.weekly?.count || 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Еженедельных</div>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
                  <div className="text-2xl font-bold text-[var(--text-primary)]">{backupStats.by_type.monthly?.count || 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Ежемесячных</div>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
                  <div className="text-2xl font-bold text-[var(--text-primary)]">{formatBytes(backupStats.total_size)}</div>
                  <div className="text-xs text-[var(--text-muted)]">Всего</div>
                </div>
              </div>
            )}
            
            {/* Actions */}
            <div className="flex gap-3 mb-5">
              <button
                onClick={handleCreateBackup}
                disabled={backupCreating}
                className="btn btn-primary flex-1"
              >
                {backupCreating ? (
                  <><div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" /> Создание...</>
                ) : (
                  '➕ Создать бекап'
                )}
              </button>
              <button
                onClick={handleCleanup}
                className="btn btn-secondary"
                title="Удалить старые бекапы по политике хранения"
              >
                🧹 Очистить
              </button>
              <button
                onClick={loadBackups}
                disabled={backupLoading}
                className="btn btn-secondary"
              >
                🔄
              </button>
            </div>
            
            {/* Retention info */}
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] mb-5">
              <p className="text-xs text-[var(--text-muted)]">
                <strong>Политика хранения:</strong> 7 ежедневных, 4 еженедельных, 12 ежемесячных. 
                Бекапы создаются автоматически в полночь.
              </p>
            </div>
            
            {/* Backup list */}
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {backupLoading ? (
                <div className="text-center py-8 text-[var(--text-muted)]">Загрузка...</div>
              ) : backups.length === 0 ? (
                <div className="text-center py-8 text-[var(--text-muted)]">Нет бекапов</div>
              ) : (
                backups.map((backup) => (
                  <div 
                    key={backup.filename}
                    className="flex items-center gap-3 p-3 rounded-xl bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                          {getBackupTypeLabel(backup.type)}
                        </span>
                        {backup.compressed && (
                          <span className="text-xs text-[var(--text-muted)]">gzip</span>
                        )}
                      </div>
                      <div className="text-xs text-[var(--text-muted)]">
                        {formatDate(backup.created_at)} • {formatBytes(backup.size)}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-1">
                      <a
                        href={getBackupDownloadUrl(backup.filename)}
                        className="p-2 rounded-lg hover:bg-[var(--bg-primary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                        title="Скачать"
                      >
                        ⬇️
                      </a>
                      
                      {confirmRestore === backup.filename ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleRestoreBackup(backup.filename)}
                            disabled={restoring === backup.filename}
                            className="px-2 py-1 rounded-lg bg-amber-500/20 text-amber-400 text-xs hover:bg-amber-500/30"
                          >
                            {restoring === backup.filename ? '...' : 'Да'}
                          </button>
                          <button
                            onClick={() => setConfirmRestore(null)}
                            className="px-2 py-1 rounded-lg bg-[var(--bg-primary)] text-[var(--text-muted)] text-xs"
                          >
                            Нет
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmRestore(backup.filename)}
                          className="p-2 rounded-lg hover:bg-[var(--bg-primary)] text-[var(--text-muted)] hover:text-amber-400 transition-colors"
                          title="Восстановить"
                        >
                          ♻️
                        </button>
                      )}
                      
                      {backup.type === 'manual' && (
                        <button
                          onClick={() => handleDeleteBackup(backup.filename)}
                          className="p-2 rounded-lg hover:bg-[var(--bg-primary)] text-[var(--text-muted)] hover:text-red-400 transition-colors"
                          title="Удалить"
                        >
                          🗑️
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* === SETUP GUIDE === */}
        <div className="card p-6 card-gradient stagger-item">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-3xl shadow-lg shadow-violet-500/40">📋</div>
            <div className="flex-1">
              <h3 className="font-semibold text-lg text-[var(--text-primary)] mb-3">Быстрая настройка</h3>
              <ol className="text-sm text-[var(--text-secondary)] space-y-3">
                {[
                  { text: 'Создайте бота через', highlight: '@BotFather', suffix: '→ скопируйте токен выше' },
                  { text: 'Получите API ключ на', highlight: 'console.groq.com', suffix: '(бесплатно)' },
                  { text: 'Узнайте свой ID у', highlight: '@userinfobot', suffix: '→ вставьте выше' },
                  { text: 'В Telegram: Настройки →', highlight: 'Telegram Business → Чат-боты', suffix: '→ добавьте бота' },
                  { text: 'Тест: напишите себе с', highlight: 'другого аккаунта', suffix: '' },
                ].map((step, i) => (
                  <li key={i} className="flex items-start gap-3 group">
                    <span className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 text-white text-xs flex items-center justify-center flex-shrink-0 mt-0.5 shadow-lg shadow-violet-500/30 group-hover:scale-110 transition-transform">{i + 1}</span>
                    <span>{step.text} <span className="text-[var(--accent)] font-medium">{step.highlight}</span> {step.suffix}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>

      </div>
      </div>
    </PageWrapper>
  );
}
