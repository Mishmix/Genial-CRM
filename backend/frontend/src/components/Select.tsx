import { useState, useRef, useEffect } from 'react';

interface Option {
  value: string;
  label: string;
  icon?: string;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  className?: string;
}

export default function Select({ value, onChange, options, placeholder = 'Выберите...', className = '' }: SelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedOption = options.find(o => o.value === value);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="input w-full text-left flex items-center justify-between gap-2"
      >
        <span className={`flex items-center gap-2 ${selectedOption ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
          {selectedOption?.icon && <span>{selectedOption.icon}</span>}
          {selectedOption?.label || placeholder}
        </span>
        <span className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 z-50 animate-fadeIn">
          <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl shadow-2xl shadow-black/50 py-2 max-h-[300px] overflow-y-auto">
            {options.map(option => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                className={`w-full px-4 py-2.5 text-left flex items-center gap-3 transition-colors ${
                  option.value === value
                    ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                }`}
              >
                {option.icon && <span className="text-lg">{option.icon}</span>}
                <span className="font-medium">{option.label}</span>
                {option.value === value && <span className="ml-auto">✓</span>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
