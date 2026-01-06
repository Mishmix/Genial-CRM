import { useState, useEffect } from 'react';
import { getSettings, updateSetting } from '../api';
import PageWrapper from '../components/PageWrapper';

const DEFAULT_PROMPTS = {
  thumbnail_classification: `Ты — строгий классификатор входящих сообщений для дизайнера YouTube-обложек.
Задача: определить категорию сообщения клиента.

## Категории (в порядке приоритета проверки)

### 1. "email_lead" - пришёл с рассылки/почты
Маркеры:
- "вы мне писали", "ви мені писали"
- "пишу с рассылки", "пишу з розсилки"
- "получил ваше письмо", "отримав ваш лист"
- "по поводу вашего письма", "щодо вашого листа"
- "с почты", "з пошти", "email", "e-mail", "імейл"
- "увидел ваше предложение", "побачив вашу пропозицію"
- "откликаюсь на ваше сообщение"
- "вы писали на почту", "писали мені на пошту"
- "из рассылки", "з розсилки"
- упоминание что где-то видел/получил сообщение от дизайнера
→ Ответ: {"category":"email_lead"}

### 2. "thumbnail" - явный запрос на превью
Маркеры:
- "превью", "превʼю", "прев'ю", "превьюшка"
- "thumbnail", "миниатюра", "мініатюра"
- "обложка для видео", "обложка на ютуб"
- "обкладинка для відео", "обкладинка на ютуб"
- "шапка и превью", "баннер и превью" (есть превью = thumbnail)
ВАЖНО: Если есть маркеры email_lead + thumbnail → всё равно "email_lead"
→ Ответ: {"category":"thumbnail"}

### 3. "other" - всё остальное
- Приветствия без контекста: "Привет", "Добрый день"
- Общие вопросы: "вы дизайнер?", "какие цены?"
- Только баннер/шапка/оформление (без превью)
- Неопределённые запросы
→ Ответ: {"category":"other"}

## Примеры
"Здравствуйте, вы мне писали на почту по поводу обложек" → {"category":"email_lead"}
"Привет, пишу с рассылки, интересует цена на превью" → {"category":"email_lead"}
"Получил ваше письмо, нужны обложки" → {"category":"email_lead"}
"Привет, нужно превью для видео" → {"category":"thumbnail"}
"Обложка на ютуб сколько стоит?" → {"category":"thumbnail"}
"Добрый день" → {"category":"other"}
"Нужен баннер для канала" → {"category":"other"}

## Правила
1. СНАЧАЛА проверяй маркеры email_lead (приоритет!)
2. Потом проверяй маркеры thumbnail
3. Всё остальное = other
4. Ответ: СТРОГО JSON, один из трёх вариантов`,
};

export default function AISettingsPage() {
  const [settings, setSettings] = useState({
    groq_api_key_set: false,
    prompt_thumbnail_classification: DEFAULT_PROMPTS.thumbnail_classification,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => { loadSettings(); }, []);

  const loadSettings = async () => {
    setLoading(true);
    try { 
      const data = await getSettings(); 
      setSettings(s => ({ 
        ...s, 
        ...data,
        prompt_thumbnail_classification: data.prompt_thumbnail_classification || DEFAULT_PROMPTS.thumbnail_classification,
      })); 
    }
    catch (err) { console.error('Failed to load settings:', err); }
    finally { setLoading(false); }
  };

  const handleSave = async (key: string, value: string) => {
    setSaving(key);
    setSaved(null);
    try { await updateSetting(key, value); setSaved(key); setTimeout(() => setSaved(null), 2000); }
    catch (err) { console.error('Failed to save:', err); }
    finally { setSaving(null); }
  };

  const handleResetPrompt = () => {
    setSettings(s => ({ ...s, prompt_thumbnail_classification: DEFAULT_PROMPTS.thumbnail_classification }));
  };

  if (loading) {
    return (
      <div className="max-w-4xl">
        <div className="mb-8"><div className="skeleton h-8 w-48 mb-2" /><div className="skeleton h-5 w-80" /></div>
        <div className="space-y-6">{[...Array(3)].map((_, i) => <div key={i} className="card p-6"><div className="skeleton h-40" /></div>)}</div>
      </div>
    );
  }

  return (
    <PageWrapper loading={loading}>
      <div className="max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-2xl shadow-lg shadow-emerald-500/30">🤖</div>
            <div>
              <h1 className="text-3xl font-bold"><span className="gradient-text">AI Настройки</span></h1>
              <p className="text-[var(--text-secondary)]">Настройка промпта для классификации</p>
            </div>
          </div>
        </div>

        {/* Status */}
        <div className="card p-5 mb-6">
          <div className="flex items-center gap-4">
            <div className={`w-3 h-3 rounded-full ${settings.groq_api_key_set ? 'bg-emerald-500' : 'bg-red-500'} animate-pulse`} />
            <span className="text-sm text-[var(--text-secondary)]">
              {settings.groq_api_key_set 
                ? 'Groq API настроен — используется openai/gpt-oss-120b' 
                : 'Groq API не настроен — перейдите в Настройки для добавления ключа'}
            </span>
            {!settings.groq_api_key_set && (
              <a href="/settings" className="btn btn-sm btn-primary ml-auto">Настроить →</a>
            )}
          </div>
        </div>

        <div className="space-y-6">
          
          {/* How it works */}
          <div className="card p-6 stagger-item">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-3xl shadow-lg shadow-violet-500/40">⚡</div>
              <div>
                <h3 className="font-semibold text-lg text-[var(--text-primary)] mb-1">Как работает классификация</h3>
                <p className="text-sm text-[var(--text-secondary)]">Бот анализирует сообщения клиентов для определения интереса к превью</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/30">
                <div className="font-semibold text-blue-400 mb-2 flex items-center gap-2">
                  <span>📧</span> "email_lead" → Mini App
                </div>
                <ul className="text-sm text-[var(--text-secondary)] space-y-1">
                  <li>• "Вы мне писали на почту"</li>
                  <li>• "Пишу с рассылки"</li>
                  <li>• "Получил ваше письмо"</li>
                  <li>• "Увидел предложение"</li>
                </ul>
              </div>
              
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                <div className="font-semibold text-emerald-400 mb-2 flex items-center gap-2">
                  <span>✅</span> "thumbnail" → Mini App
                </div>
                <ul className="text-sm text-[var(--text-secondary)] space-y-1">
                  <li>• "Сколько стоит превью?"</li>
                  <li>• "Need YouTube thumbnail"</li>
                  <li>• "обкладинка для відео"</li>
                  <li>• "шапка и превью"</li>
                </ul>
              </div>
              
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <div className="font-semibold text-amber-400 mb-2 flex items-center gap-2">
                  <span>⏸️</span> "other" → Ждать ещё
                </div>
                <ul className="text-sm text-[var(--text-secondary)] space-y-1">
                  <li>• "Привет"</li>
                  <li>• "Вы дизайнер?"</li>
                  <li>• "Нужен баннер"</li>
                  <li>• "оформление канала"</li>
                </ul>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-sm text-[var(--text-secondary)]">
              <strong className="text-[var(--text-primary)]">Условия остановки:</strong>
              <ul className="mt-2 space-y-1">
                <li>• Если вы ответили клиенту → бот перестаёт анализировать навсегда</li>
                <li>• Если Mini App отправлен → бот перестаёт анализировать навсегда</li>
                <li>• Обрабатываются только новые чаты или неактивные 6+ месяцев</li>
              </ul>
            </div>
          </div>

          {/* Thumbnail Classification Prompt */}
          <div className="card p-6 stagger-item">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-2xl shadow-lg">🎯</div>
                <div>
                  <h3 className="font-semibold text-lg text-[var(--text-primary)]">Промпт классификации</h3>
                  <p className="text-sm text-[var(--text-secondary)]">Системный промпт для GPT-OSS-120B</p>
                </div>
              </div>
              <button onClick={handleResetPrompt} className="btn btn-ghost btn-sm">↺ Сбросить</button>
            </div>
            
            <textarea
              value={settings.prompt_thumbnail_classification}
              onChange={(e) => setSettings(s => ({ ...s, prompt_thumbnail_classification: e.target.value }))}
              className="input mb-3 font-mono text-sm"
              rows={18}
            />
            
            <div className="flex items-center justify-between">
              <p className="text-xs text-[var(--text-muted)]">
                Должен возвращать: <code className="px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-blue-400">{`{"category":"email_lead"}`}</code>, <code className="px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-emerald-400">{`{"category":"thumbnail"}`}</code> или <code className="px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-amber-400">{`{"category":"other"}`}</code>
              </p>
              <button 
                onClick={() => handleSave('prompt_thumbnail_classification', settings.prompt_thumbnail_classification)} 
                disabled={saving === 'prompt_thumbnail_classification'} 
                className="btn btn-primary"
              >
                {saving === 'prompt_thumbnail_classification' ? 'Сохранение...' : saved === 'prompt_thumbnail_classification' ? '✓ Сохранено' : 'Сохранить промпт'}
              </button>
            </div>
          </div>

          {/* Tips */}
          <div className="card p-6 card-gradient stagger-item">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-3xl shadow-lg shadow-violet-500/40">💡</div>
              <div>
                <h3 className="font-semibold text-lg text-[var(--text-primary)] mb-3">Советы по промпту</h3>
                <ul className="text-sm text-[var(--text-secondary)] space-y-2">
                  {[
                    'Будьте строги — лучше пропустить, чем отправить Mini App не тому',
                    'Добавьте больше примеров на вашем языке при необходимости',
                    'Сохраняйте требование формата JSON',
                    'Протестируйте с разными типами сообщений перед запуском',
                  ].map((tip, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

        </div>
      </div>
    </PageWrapper>
  );
}
