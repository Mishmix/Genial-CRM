import { useState, useEffect, useRef } from 'react';

interface DatePickerProps {
  value: string;
  onChange: (date: string) => void;
  placeholder?: string;
  minDate?: string;
  className?: string;
  showTime?: boolean;
}

const MONTHS_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

const DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

// Форматирует дату в YYYY-MM-DD без проблем с часовым поясом
function formatDateLocal(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function DatePicker({ 
  value, 
  onChange, 
  placeholder = 'Выберите дату', 
  minDate, 
  className = '',
  showTime = false 
}: DatePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() => {
    if (value) {
      const d = new Date(value);
      return new Date(d.getFullYear(), d.getMonth(), 1);
    }
    return new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  });
  const [selectedTime, setSelectedTime] = useState(() => {
    if (value && value.includes('T')) {
      const timePart = value.split('T')[1];
      if (timePart) return timePart.slice(0, 5);
    }
    return '12:00';
  });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    
    // Понедельник = 0, Воскресенье = 6
    let startDay = firstDay.getDay() - 1;
    if (startDay < 0) startDay = 6;
    
    const days: (number | null)[] = [];
    for (let i = 0; i < startDay; i++) days.push(null);
    for (let i = 1; i <= daysInMonth; i++) days.push(i);
    return days;
  };

  const handleSelectDay = (day: number) => {
    const selected = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
    const dateStr = formatDateLocal(selected);
    
    if (showTime) {
      onChange(`${dateStr}T${selectedTime}`);
    } else {
      onChange(dateStr);
    }
    setIsOpen(false);
  };

  const handleTimeChange = (time: string) => {
    setSelectedTime(time);
    if (value) {
      const datePart = value.split('T')[0];
      onChange(`${datePart}T${time}`);
    }
  };

  const isToday = (day: number) => {
    const today = new Date();
    return day === today.getDate() && 
           viewDate.getMonth() === today.getMonth() && 
           viewDate.getFullYear() === today.getFullYear();
  };

  const isSelected = (day: number) => {
    if (!value) return false;
    const datePart = value.split('T')[0];
    const [year, month, selectedDay] = datePart.split('-').map(Number);
    return day === selectedDay && 
           viewDate.getMonth() === month - 1 && 
           viewDate.getFullYear() === year;
  };

  const isPast = (day: number) => {
    if (!minDate) return false;
    const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
    const [minYear, minMonth, minDay] = minDate.split('-').map(Number);
    const min = new Date(minYear, minMonth - 1, minDay);
    return date < min;
  };

  const formatDisplayDate = (dateStr: string) => {
    const datePart = dateStr.split('T')[0];
    const [year, month, day] = datePart.split('-').map(Number);
    const monthName = MONTHS_RU[month - 1].toLowerCase();
    let result = `${day} ${monthName}`;
    if (showTime && dateStr.includes('T')) {
      const timePart = dateStr.split('T')[1];
      if (timePart) result += `, ${timePart.slice(0, 5)}`;
    }
    return result;
  };

  const setQuickDate = (daysToAdd: number) => {
    const d = new Date();
    d.setDate(d.getDate() + daysToAdd);
    const dateStr = formatDateLocal(d);
    if (showTime) {
      onChange(`${dateStr}T${selectedTime}`);
    } else {
      onChange(dateStr);
    }
    setIsOpen(false);
  };

  const days = getDaysInMonth(viewDate);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl text-left flex items-center justify-between text-sm transition-all hover:border-[var(--accent)]/50 focus:border-[var(--accent)] focus:ring-0 focus:outline-none"
      >
        <span className={value ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}>
          {value ? formatDisplayDate(value) : placeholder}
        </span>
        <span className="text-lg">📅</span>
      </button>

      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-2 z-[9999]">
          <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl shadow-2xl shadow-black/50 overflow-hidden">
            {/* Quick buttons */}
            <div className="p-3 border-b border-[var(--border)] bg-[var(--bg-secondary)]/50">
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Сегодня', days: 0 },
                  { label: 'Завтра', days: 1 },
                  { label: '+2 дня', days: 2 },
                  { label: '+7 дней', days: 7 },
                ].map(({ label, days }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setQuickDate(days)}
                    className="py-2 px-2 text-xs font-medium rounded-lg bg-[var(--bg-hover)] hover:bg-[var(--accent)]/20 hover:text-[var(--accent)] transition-all"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Calendar */}
            <div className="p-4">
              {/* Month navigation */}
              <div className="flex items-center justify-between mb-4">
                <button
                  type="button"
                  onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))}
                  className="w-8 h-8 rounded-lg hover:bg-[var(--bg-hover)] flex items-center justify-center transition-colors text-lg"
                >
                  ‹
                </button>
                <span className="font-semibold text-[var(--text-primary)]">
                  {MONTHS_RU[viewDate.getMonth()]} {viewDate.getFullYear()}
                </span>
                <button
                  type="button"
                  onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))}
                  className="w-8 h-8 rounded-lg hover:bg-[var(--bg-hover)] flex items-center justify-center transition-colors text-lg"
                >
                  ›
                </button>
              </div>

              {/* Days header */}
              <div className="grid grid-cols-7 gap-1 mb-2">
                {DAYS_RU.map(day => (
                  <div key={day} className="text-center text-xs text-[var(--text-muted)] font-medium py-1">
                    {day}
                  </div>
                ))}
              </div>

              {/* Days grid */}
              <div className="grid grid-cols-7 gap-1">
                {days.map((day, idx) => (
                  <div key={idx} className="aspect-square">
                    {day !== null && (
                      <button
                        type="button"
                        onClick={() => !isPast(day) && handleSelectDay(day)}
                        disabled={isPast(day)}
                        className={`w-full h-full rounded-lg text-sm font-medium transition-all flex items-center justify-center ${
                          isSelected(day)
                            ? 'bg-[var(--accent)] text-white'
                            : isToday(day)
                            ? 'bg-[var(--accent)]/20 text-[var(--accent)] font-bold'
                            : isPast(day)
                            ? 'text-[var(--text-muted)]/30 cursor-not-allowed'
                            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
                        }`}
                      >
                        {day}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Time picker */}
            {showTime && (
              <div className="p-4 border-t border-[var(--border)] bg-[var(--bg-secondary)]/30">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-[var(--text-muted)]">🕐 Время:</span>
                  <input
                    type="time"
                    value={selectedTime}
                    onChange={(e) => handleTimeChange(e.target.value)}
                    className="flex-1 px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
