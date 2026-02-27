/**
 * API client for CRM Bot backend
 */

// В production используем переменную окружения, в dev - относительный путь (через proxy)
export const API_BASE = import.meta.env.VITE_API_URL || '/api';

interface ApiError {
  detail: string;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Auth
export async function authTelegram(initData: string) {
  return request<{ success: boolean; user_id?: number; username?: string }>('/auth/telegram', {
    method: 'POST',
    body: JSON.stringify({ init_data: initData }),
  });
}

export async function authPassword(password: string, rememberMe: boolean = true) {
  return request<{ success: boolean }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password, remember_me: rememberMe }),
  });
}

export async function logout() {
  return request<{ success: boolean }>('/auth/logout', { method: 'POST' });
}

export async function getMe() {
  return request<{ authenticated: boolean; auth_type: string; telegram_user_id?: number }>('/auth/me');
}

// Clients
export interface Client {
  id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string;
  last_name: string | null;
  status: string;
  unread_count: number;
  last_message_at: string | null;
  avatar_local_path: string | null;
  tags: Tag[];
  is_archived: boolean;
  deadline: string | null;
  lost_reason: string | null;
  first_seen_at: string | null;
  message_count: number;
}

export interface ClientDetail extends Client {
  language_code: string | null;
  notes: string | null;
  source: string | null;
  created_at: string;
  updated_at: string | null;
  business_connection_id: string | null;
  messages: Message[];
  reminders: Reminder[];
  merged_from: string | null;
  lost_reason: string | null;
  deadline: string | null;
}

export interface Message {
  id: number;
  client_id: number;
  direction: 'in' | 'out';
  text: string | null;
  telegram_message_id: number | null;
  sent_at: string;
}

export interface Tag {
  id: number;
  name: string;
  color: string;
}

export async function getClientsStats() {
  return request<{ total: number; new: number; sent_price: number; ordered: number; rejected: number; unread: number }>('/clients/stats');
}

export async function getClients(params: {
  page?: number;
  per_page?: number;
  status?: string;
  has_unread?: boolean;
  tag_ids?: string;
  include_archived?: boolean;
} = {}) {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.per_page) query.set('per_page', String(params.per_page));
  if (params.status) query.set('status', params.status);
  if (params.has_unread !== undefined) query.set('has_unread', String(params.has_unread));
  if (params.tag_ids) query.set('tag_ids', params.tag_ids);
  if (params.include_archived !== undefined) query.set('include_archived', String(params.include_archived));

  return request<{ items: Client[]; total: number; page: number; per_page: number }>(
    `/clients?${query}`
  );
}

export async function searchClients(q: string) {
  return request<{ items: Client[]; query: string }>(`/clients/search?q=${encodeURIComponent(q)}`);
}

export async function getClient(id: number) {
  return request<ClientDetail>(`/clients/${id}`);
}

export async function updateClient(id: number, data: {
  status?: string;
  notes?: string;
  tag_ids?: number[];
  is_archived?: boolean;
  lost_reason?: string;
  deadline?: string;
}) {
  return request<ClientDetail>(`/clients/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function markClientRead(id: number) {
  return request<{ success: boolean }>(`/clients/${id}/read`, { method: 'POST' });
}

export async function sendMessage(clientId: number, text: string) {
  return request<Message>(`/clients/${clientId}/send`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

// Tags
export async function getTags() {
  return request<{ items: Tag[] }>('/tags');
}

export async function createTag(name: string, color: string = '#6366f1') {
  return request<Tag>('/tags', {
    method: 'POST',
    body: JSON.stringify({ name, color }),
  });
}

export async function deleteTag(id: number) {
  return request<{ success: boolean }>(`/tags/${id}`, { method: 'DELETE' });
}

// Templates
export interface Template {
  id: number;
  name: string;
  language: string;
  content: string;
  is_auto_reply: boolean;
  is_active: boolean;
  created_at: string;
}

export async function getTemplates(params: { language?: string; is_auto_reply?: boolean } = {}) {
  const query = new URLSearchParams();
  if (params.language) query.set('language', params.language);
  if (params.is_auto_reply !== undefined) query.set('is_auto_reply', String(params.is_auto_reply));

  return request<{ items: Template[] }>(`/templates?${query}`);
}

export async function getTemplate(id: number) {
  return request<Template>(`/templates/${id}`);
}

export async function createTemplate(data: {
  name: string;
  language: string;
  content: string;
  is_auto_reply: boolean;
  is_active: boolean;
}) {
  return request<Template>('/templates', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTemplate(id: number, data: Partial<{
  name: string;
  language: string;
  content: string;
  is_auto_reply: boolean;
  is_active: boolean;
}>) {
  return request<Template>(`/templates/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteTemplate(id: number) {
  return request<{ success: boolean }>(`/templates/${id}`, { method: 'DELETE' });
}

// Settings
export async function getSettings() {
  return request<{ portfolio_url: string; auto_reply_enabled: boolean; social_proof: string; prompt_thumbnail_classification?: string }>('/settings');
}

export async function updateSetting(key: string, value: string) {
  return request<{ success: boolean }>('/settings', {
    method: 'PUT',
    body: JSON.stringify({ key, value }),
  });
}

// Reminders
export interface Reminder {
  id: number;
  client_id: number;
  reminder_type: 'dm' | 'sticky';
  text: string;
  remind_at: string;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
}

export async function getReminders(params: { client_id?: number; is_completed?: boolean } = {}) {
  const query = new URLSearchParams();
  if (params.client_id) query.set('client_id', String(params.client_id));
  if (params.is_completed !== undefined) query.set('is_completed', String(params.is_completed));

  return request<Reminder[]>(`/reminders?${query}`);
}

export async function getPendingReminders() {
  return request<Reminder[]>('/reminders/pending');
}

export async function createReminder(data: {
  client_id: number;
  reminder_type: 'dm' | 'sticky';
  text: string;
  remind_at: string;
}) {
  return request<Reminder>('/reminders', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function completeReminder(id: number) {
  return request<Reminder>(`/reminders/${id}/complete`, { method: 'POST' });
}

export async function deleteReminder(id: number) {
  return request<{ success: boolean }>(`/reminders/${id}`, { method: 'DELETE' });
}

// Client actions
export async function archiveClient(id: number) {
  return request<{ success: boolean }>(`/clients/${id}/archive`, { method: 'POST' });
}

export async function unarchiveClient(id: number) {
  return request<{ success: boolean }>(`/clients/${id}/unarchive`, { method: 'POST' });
}

export async function deleteClient(id: number) {
  return request<{ success: boolean }>(`/clients/${id}`, { method: 'DELETE' });
}

export async function mergeClients(sourceIds: number[], targetId: number) {
  return request<ClientDetail>('/clients/merge', {
    method: 'POST',
    body: JSON.stringify({ source_client_ids: sourceIds, target_client_id: targetId }),
  });
}


// Orders
export interface Order {
  id: number;
  client_id: number;
  service_type: 'thumbnail' | 'banner' | 'logo' | 'channel_design' | 'other';
  quantity: number;
  amount: number | null;
  currency: string;
  has_ab_test: boolean;
  has_title: boolean;
  has_rush: boolean;
  deadline_type: 'exact' | 'flexible' | null;
  deadline_date: string | null;
  deadline_range: string | null;
  deadline_custom: string | null;
  deadline_calculated: string | null;
  status: 'pending' | 'completed' | 'cancelled' | 'refunded' | 'deleted';
  notes: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RejectionReason {
  id: number;
  code: string;
  label: string;
  emoji: string | null;
}

export async function getOrders(params: { client_id?: number; conversation_id?: number; status?: string } = {}) {
  const query = new URLSearchParams();
  if (params.client_id) query.set('client_id', String(params.client_id));
  if (params.conversation_id) query.set('conversation_id', String(params.conversation_id));
  if (params.status) query.set('status', params.status);

  return request<{ items: Order[]; total: number }>(`/orders?${query}`);
}

export async function getOrder(id: number) {
  return request<Order>(`/orders/${id}`);
}

export async function createOrder(data: {
  client_id: number;
  conversation_id?: number;
  service_type: string;
  quantity?: number;
  amount?: number;
  currency?: string;
  has_ab_test?: boolean;
  has_title?: boolean;
  has_rush?: boolean;
  deadline_type?: 'exact' | 'flexible';
  deadline_date?: string;
  deadline_range?: string;
  deadline_custom?: string;
  notes?: string;
}) {
  return request<Order>('/orders', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateOrder(id: number, data: Partial<{
  service_type: string;
  quantity: number;
  amount: number;
  has_ab_test: boolean;
  has_title: boolean;
  has_rush: boolean;
  deadline_type: string;
  deadline_date: string;
  deadline_range: string;
  deadline_custom: string;
  status: string;
  notes: string;
}>) {
  return request<Order>(`/orders/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteOrder(id: number) {
  return request<{ success: boolean }>(`/orders/${id}`, { method: 'DELETE' });
}

export async function getOrderStats(clientId: number) {
  return request<{ total_orders: number; completed_orders: number; total_spent: number }>(
    `/orders/stats/${clientId}`
  );
}

export async function getRejectionReasons() {
  return request<{ items: RejectionReason[] }>('/orders/rejection-reasons');
}

// Manual client creation
export async function createManualClient(data: {
  first_name: string;
  last_name?: string;
  username?: string;
  source: 'whatsapp' | 'instagram' | 'telegram' | 'other';
  phone?: string;
  notes?: string;
}) {
  return request<ClientDetail>('/clients/manual', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// Fetch avatar for a client
export async function fetchClientAvatar(clientId: number) {
  return request<{ success: boolean; avatar_url?: string; message?: string }>(
    `/clients/${clientId}/fetch-avatar`,
    { method: 'POST' }
  );
}


// ============ Conversations ============

export interface ConversationClient {
  id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string;
  last_name: string | null;
  avatar_local_path: string | null;
  status: string;
  sticky_note: string | null;
  total_orders: number;
  total_spent: number;
  tags: Tag[];
}

export interface Conversation {
  id: number;
  client_id: number;
  source: string | null;
  category: string | null;
  status: string;
  rejection_reason: string | null;
  rejection_custom: string | null;
  unread_count: number;
  auto_reply_sent: boolean;
  owner_replied: boolean;
  started_at: string | null;
  owner_replied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  client: ConversationClient | null;
  orders_count: number;
  total_amount: number;
}

export interface ConversationMessage {
  id: number;
  direction: string;
  text: string | null;
  message_type: string;
  sent_at: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}

export async function getConversations(params: {
  status?: string;
  category?: string;
  period?: string;
  has_unread?: boolean;
  include_deleted?: boolean;
  skip?: number;
  limit?: number;
} = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.category) query.set('category', params.category);
  if (params.period) query.set('period', params.period);
  if (params.has_unread !== undefined) query.set('has_unread', String(params.has_unread));
  if (params.include_deleted !== undefined) query.set('include_deleted', String(params.include_deleted));
  if (params.skip !== undefined) query.set('skip', String(params.skip));
  if (params.limit !== undefined) query.set('limit', String(params.limit));

  return request<{ items: Conversation[]; total: number }>(`/conversations?${query}`);
}

export async function getConversation(id: number) {
  return request<ConversationDetail>(`/conversations/${id}`);
}

export async function createConversation(data: {
  client_id: number;
  source?: string;
  category?: string;
}) {
  return request<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateConversation(id: number, data: {
  status?: string;
  category?: string;
  rejection_reason?: string;
  rejection_custom?: string;
}) {
  return request<Conversation>(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteConversation(id: number, reason?: string) {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : '';
  return request<{ success: boolean }>(`/conversations/${id}${query}`, { method: 'DELETE' });
}

export async function markConversationRead(id: number) {
  return request<{ success: boolean }>(`/conversations/${id}/mark-read`, { method: 'POST' });
}

export interface AnalyzeOrderResult {
  success: boolean;
  message: string;
  order?: {
    id: number;
    service_type: string;
    quantity: number;
    deadline_date: string | null;
    confidence: number | null;
  };
}

export async function analyzeConversationOrder(id: number): Promise<AnalyzeOrderResult> {
  return request<AnalyzeOrderResult>(`/conversations/${id}/analyze-order`, { method: 'POST' });
}


// ============ Todoist ============

export interface TodoistConfig {
  api_token_masked: string;
  api_token_set: boolean;
  project_id: string;
  section_today_id: string;
  section_not_today_id: string;
  enabled: boolean;
}

export interface TodoistProject {
  id: string;
  name: string;
  color: string;
}

export interface TodoistSection {
  [name: string]: string;
}

export async function getTodoistConfig() {
  return request<TodoistConfig>('/todoist/config');
}

export async function updateTodoistConfig(data: {
  api_token?: string;
  project_id?: string;
  section_today_id?: string;
  section_not_today_id?: string;
  enabled?: boolean;
}) {
  return request<{ success: boolean }>('/todoist/config', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function testTodoistConnection() {
  return request<{ success: boolean; message: string }>('/todoist/test');
}

export async function getTodoistProjects() {
  return request<{ items: TodoistProject[] }>('/todoist/projects');
}

export async function getTodoistSections(projectId: string) {
  return request<{ items: TodoistSection }>(`/todoist/sections/${projectId}`);
}


// ============ Import ============

export interface ImportStatus {
  running: boolean;
  progress: number;
  total: number;
  current_chat: string;
  imported_clients: number;
  imported_messages: number;
  skipped_messages: number;
  errors: string[];
}

export async function getImportStatus() {
  return request<ImportStatus>('/import/status');
}

export async function importTelegramExport(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${API_BASE}/import/telegram/sync`;

  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Import failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}


// ============ Backup ============

export interface Backup {
  filename: string;
  type: string;
  size: number;
  compressed: boolean;
  created_at: string;
}

export interface BackupStats {
  total_count: number;
  total_size: number;
  by_type: Record<string, { count: number; size: number }>;
  latest: Backup | null;
  backup_dir: string;
  retention: Record<string, number>;
}

export async function getBackups() {
  return request<{ backups: Backup[] }>('/backup/list');
}

export async function getBackupStats() {
  return request<BackupStats>('/backup/stats');
}

export async function createBackup(backupType: string = 'manual', compress: boolean = true) {
  return request<Backup>('/backup/create', {
    method: 'POST',
    body: JSON.stringify({ backup_type: backupType, compress }),
  });
}

export async function deleteBackup(filename: string) {
  return request<{ success: boolean; message: string }>(`/backup/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
}

export async function restoreBackup(filename: string) {
  return request<{ success: boolean; message: string }>(`/backup/restore/${encodeURIComponent(filename)}`, {
    method: 'POST',
  });
}

export async function cleanupBackups() {
  return request<{ deleted: number; message: string }>('/backup/cleanup', {
    method: 'POST',
  });
}

export function getBackupDownloadUrl(filename: string) {
  return `/api/backup/download/${encodeURIComponent(filename)}`;
}
