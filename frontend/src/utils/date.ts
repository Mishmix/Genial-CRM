// Date utilities with Georgia timezone (UTC+4)
const TIMEZONE = 'Asia/Tbilisi';

// Parse date string as UTC (backend returns UTC without Z suffix)
export function parseAsUTC(dateStr: string): Date {
  // If already has timezone info, parse as is
  if (dateStr.endsWith('Z') || dateStr.includes('+') || dateStr.includes('-', 10)) {
    return new Date(dateStr);
  }
  // Otherwise treat as UTC by adding Z
  return new Date(dateStr + 'Z');
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = parseAsUTC(dateStr);
  return date.toLocaleString('ru-RU', {
    timeZone: TIMEZONE,
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = parseAsUTC(dateStr);
  return date.toLocaleTimeString('ru-RU', {
    timeZone: TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = parseAsUTC(dateStr);
  return date.toLocaleDateString('ru-RU', {
    timeZone: TIMEZONE,
    day: 'numeric',
    month: 'short',
  });
}

export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  
  // Parse the date as UTC
  const date = parseAsUTC(dateStr);
  const now = new Date();
  
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 0) return 'только что'; // Future date edge case
  if (diffMins < 1) return 'только что';
  if (diffMins < 60) return `${diffMins} мин назад`;
  if (diffHours < 24) return `${diffHours} ч назад`;
  if (diffDays === 1) return 'вчера';
  if (diffDays < 7) return `${diffDays} дн назад`;
  
  return formatDate(dateStr);
}

export function isToday(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  const date = parseAsUTC(dateStr);
  const today = new Date();
  return date.toLocaleDateString('ru-RU', { timeZone: TIMEZONE }) === 
         today.toLocaleDateString('ru-RU', { timeZone: TIMEZONE });
}

export function isTomorrow(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  const date = parseAsUTC(dateStr);
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return date.toLocaleDateString('ru-RU', { timeZone: TIMEZONE }) === 
         tomorrow.toLocaleDateString('ru-RU', { timeZone: TIMEZONE });
}
