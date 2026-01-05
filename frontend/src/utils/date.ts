// Date utilities with Georgia timezone (UTC+4)
const TIMEZONE = 'Asia/Tbilisi';

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
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
  const date = new Date(dateStr);
  return date.toLocaleTimeString('ru-RU', {
    timeZone: TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('ru-RU', {
    timeZone: TIMEZONE,
    day: 'numeric',
    month: 'short',
  });
}

export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  
  // Parse the date and get current time in Georgia timezone
  const date = new Date(dateStr);
  
  // Get current time in Georgia timezone
  const nowInGeorgia = new Date(new Date().toLocaleString('en-US', { timeZone: TIMEZONE }));
  const dateInGeorgia = new Date(date.toLocaleString('en-US', { timeZone: TIMEZONE }));
  
  const diffMs = nowInGeorgia.getTime() - dateInGeorgia.getTime();
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
  const date = new Date(dateStr);
  const today = new Date();
  return date.toLocaleDateString('ru-RU', { timeZone: TIMEZONE }) === 
         today.toLocaleDateString('ru-RU', { timeZone: TIMEZONE });
}

export function isTomorrow(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return date.toLocaleDateString('ru-RU', { timeZone: TIMEZONE }) === 
         tomorrow.toLocaleDateString('ru-RU', { timeZone: TIMEZONE });
}
