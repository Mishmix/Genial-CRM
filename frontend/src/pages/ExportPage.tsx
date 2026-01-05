import { useState } from 'react';
import PageWrapper from '../components/PageWrapper';
import DatePicker from '../components/DatePicker';
import Select from '../components/Select';

const FORMAT_OPTIONS = [
  { value: 'csv', label: 'CSV', icon: '📊' },
  { value: 'json', label: 'JSON', icon: '📋' },
];

const DATA_OPTIONS = [
  { value: 'clients', label: 'Клиенты', icon: '👥' },
  { value: 'orders', label: 'Заказы', icon: '📦' },
  { value: 'messages', label: 'Сообщения', icon: '💬' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы', icon: '📊' },
  { value: 'new', label: 'Новый', icon: '✨' },
  { value: 'sent_price', label: 'Отправлен прайс', icon: '💰' },
  { value: 'ordered', label: 'Заказал', icon: '✅' },
  { value: 'rejected', label: 'Отказ', icon: '❌' },
];

export default function ExportPage() {
  const [format, setFormat] = useState('csv');
  const [dataType, setDataType] = useState('clients');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [status, setStatus] = useState('');
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.set('format', format);
      params.set('data_type', dataType);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      if (status) params.set('status', status);

      const response = await fetch(`/api/export?${params}`, {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `crm_export_${dataType}_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      console.error('Export failed:', err);
      alert('Ошибка экспорта');
    } finally {
      setExporting(false);
    }
  };

  return (
    <PageWrapper>
      <div className="max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-2xl shadow-lg shadow-cyan-500/30">📤</div>
            <div>
              <h1 className="text-3xl font-bold"><span className="gradient-text-cyan">Экспорт данных</span></h1>
              <p className="text-[var(--text-secondary)]">Выгрузите данные в удобном формате</p>
            </div>
          </div>
        </div>

        <div className="card p-6 space-y-6">
          {/* Data type */}
          <div>
            <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">
              Тип данных
            </label>
            <div className="grid grid-cols-3 gap-3">
              {DATA_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setDataType(opt.value)}
                  className={`p-4 rounded-xl border text-center transition-all ${
                    dataType === opt.value
                      ? 'border-[var(--accent)] bg-[var(--accent)]/20 shadow-lg shadow-[var(--accent)]/20'
                      : 'border-[var(--border)] hover:bg-[var(--bg-hover)] hover:border-[var(--border-hover)]'
                  }`}
                >
                  <div className="text-2xl mb-2">{opt.icon}</div>
                  <div className="font-medium text-sm">{opt.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Format */}
          <div>
            <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">
              Формат файла
            </label>
            <Select
              value={format}
              onChange={setFormat}
              options={FORMAT_OPTIONS}
            />
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">
                Дата от
              </label>
              <DatePicker
                value={dateFrom}
                onChange={setDateFrom}
                placeholder="Начало периода"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">
                Дата до
              </label>
              <DatePicker
                value={dateTo}
                onChange={setDateTo}
                placeholder="Конец периода"
              />
            </div>
          </div>

          {/* Status filter (for clients) */}
          {dataType === 'clients' && (
            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3 block">
                Фильтр по статусу
              </label>
              <Select
                value={status}
                onChange={setStatus}
                options={STATUS_OPTIONS}
                placeholder="Все статусы"
              />
            </div>
          )}

          {/* Export button */}
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="btn btn-primary w-full py-4 text-base"
          >
            {exporting ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Экспортируем...
              </>
            ) : (
              <>📤 Скачать {format.toUpperCase()}</>
            )}
          </button>

          {/* Info */}
          <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)]">
            <div className="flex items-start gap-3">
              <span className="text-lg">💡</span>
              <div className="text-sm text-[var(--text-secondary)]">
                <p className="mb-2">Экспорт включает:</p>
                <ul className="list-disc list-inside space-y-1 text-[var(--text-muted)]">
                  {dataType === 'clients' && (
                    <>
                      <li>Имя, username, Telegram ID</li>
                      <li>Статус, теги, заметки</li>
                      <li>Дата первого и последнего сообщения</li>
                    </>
                  )}
                  {dataType === 'orders' && (
                    <>
                      <li>Тип услуги, количество, сумма</li>
                      <li>Статус заказа, дедлайн</li>
                      <li>Данные клиента</li>
                    </>
                  )}
                  {dataType === 'messages' && (
                    <>
                      <li>Текст сообщения, направление</li>
                      <li>Дата и время отправки</li>
                      <li>Данные клиента</li>
                    </>
                  )}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
