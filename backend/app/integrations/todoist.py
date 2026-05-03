"""
Todoist Integration Module
Синхронизация заказов CRM с проектом Todoist
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

TODOIST_API_URL = "https://api.todoist.com/api/v1"


class TodoistClient:
    """Client for Todoist REST API v2"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make request to Todoist API"""
        url = f"{TODOIST_API_URL}/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=self.headers, params=data)
                elif method == "POST":
                    response = await client.post(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=self.headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                if response.status_code == 204:
                    return {"success": True}
                elif response.status_code >= 400:
                    logger.error(f"Todoist API error: {response.status_code} - {response.text}")
                    return None
                
                return response.json()
            except Exception as e:
                logger.error(f"Todoist request failed: {e}")
                return None
    
    def _extract_list(self, result) -> List[Dict]:
        """Extract list from API response (handles both array and paginated object)"""
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("items", result.get("results", []))
        return []

    async def get_projects(self) -> List[Dict]:
        """Get all projects"""
        result = await self._request("GET", "projects")
        return self._extract_list(result)

    async def get_sections(self, project_id: str) -> List[Dict]:
        """Get all sections for a project"""
        result = await self._request("GET", "sections", {"project_id": project_id})
        return self._extract_list(result)
    
    async def create_task(
        self,
        content: str,
        description: str = "",
        project_id: Optional[str] = None,
        section_id: Optional[str] = None,
        due_string: Optional[str] = None,
        due_date: Optional[str] = None,
        due_datetime: Optional[str] = None,
        priority: int = 1,
        labels: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Create a new task in Todoist"""
        data = {
            "content": content,
            "priority": priority
        }
        
        if description:
            data["description"] = description
        if project_id:
            data["project_id"] = project_id
        if section_id:
            data["section_id"] = section_id
        if due_string:
            data["due_string"] = due_string
        if due_date:
            data["due_date"] = due_date
        if due_datetime:
            data["due_datetime"] = due_datetime
        if labels:
            data["labels"] = labels
        
        return await self._request("POST", "tasks", data)
    
    async def update_task(
        self,
        task_id: str,
        content: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        due_string: Optional[str] = None,
        priority: Optional[int] = None,
        labels: Optional[List[str]] = None,
        section_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update an existing task in Todoist (preserves task ID, comments, subtasks)."""
        data = {}
        if content is not None:
            data["content"] = content
        if description is not None:
            data["description"] = description
        if due_date is not None:
            data["due_date"] = due_date
        if due_string is not None:
            data["due_string"] = due_string
        if priority is not None:
            data["priority"] = priority
        if labels is not None:
            data["labels"] = labels
        if section_id is not None:
            data["section_id"] = section_id
        
        if not data:
            return None
        
        return await self._request("POST", f"tasks/{task_id}", data)
    
    async def get_tasks(self, project_id: Optional[str] = None) -> List[Dict]:
        """Get active tasks"""
        params = {}
        if project_id:
            params["project_id"] = project_id
        
        result = await self._request("GET", "tasks", params)
        return self._extract_list(result)
    
    async def close_task(self, task_id: str) -> bool:
        """Mark task as complete"""
        result = await self._request("POST", f"tasks/{task_id}/close")
        return result is not None
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task"""
        result = await self._request("DELETE", f"tasks/{task_id}")
        return result is not None
    
    async def test_connection(self) -> bool:
        """Test if API token is valid"""
        projects = await self.get_projects()
        return projects is not None


# Названия услуг на русском
SERVICE_NAMES = {
    "thumbnail": "Превью",
    "banner": "Баннер", 
    "logo": "Лого",
    "avatar": "Аватарка",
    "channel_design": "Оформление канала",
    "cover": "Обложка",
    "template": "Шаблоны",
    "other": "Другое"
}


async def create_task_from_order(
    api_token: str,
    project_id: str,
    section_today_id: str,
    section_not_today_id: str,
    client_name: str,
    service_type: str,
    quantity: int,
    deadline: Optional[datetime]
) -> Optional[Dict]:
    """
    Создать задачу в Todoist из заказа CRM
    
    Логика секций:
    - Если дедлайн сегодня → секция "Today"
    - Если дедлайн не сегодня или нет дедлайна → секция "Not Today"
    """
    client = TodoistClient(api_token)
    
    # Название услуги
    service_name = SERVICE_NAMES.get(service_type, service_type)
    
    # Формат: "Превью Иван Иванов" или "3 Превью Иван Иванов"
    if quantity > 1:
        content = f"{quantity} {service_name} {client_name}"
    else:
        content = f"{service_name} {client_name}"
    
    # Определяем секцию по дедлайну (если секции настроены)
    section_id = None
    if section_today_id or section_not_today_id:
        today = date.today()
        if deadline and deadline.date() == today:
            section_id = section_today_id or section_not_today_id
        else:
            section_id = section_not_today_id or section_today_id
    
    # Формируем дату для Todoist
    due_date = None
    if deadline:
        due_date = deadline.strftime("%Y-%m-%d")
    
    return await client.create_task(
        content=content,
        project_id=project_id,
        section_id=section_id,
        due_date=due_date,
        priority=1
    )


async def get_project_sections(api_token: str, project_id: str) -> Dict[str, str]:
    """Получить секции проекта и вернуть маппинг имя -> id"""
    client = TodoistClient(api_token)
    sections = await client.get_sections(project_id)

    return {s["name"]: s["id"] for s in sections}


# ===========================================================================
# Sync Manager helpers — used by /api/todoist/sync/*
# ===========================================================================


async def list_active_tasks(
    api_token: str,
    project_id: str,
) -> List[Dict[str, Any]]:
    """All pending tasks in the configured project, normalized for the sync routine.

    Each item: {id, content, due_date, due_string, section_id, section_name,
                labels, created_at, url}
    """
    client = TodoistClient(api_token)
    sections = await client.get_sections(project_id)
    section_name_by_id = {s["id"]: s.get("name") for s in sections}

    raw = await client.get_tasks(project_id=project_id)
    out: List[Dict[str, Any]] = []
    for t in raw:
        due = t.get("due") or {}
        out.append({
            "id": t.get("id"),
            "content": t.get("content"),
            "due_date": due.get("date"),
            "due_string": due.get("string"),
            "section_id": t.get("section_id"),
            "section_name": section_name_by_id.get(t.get("section_id")),
            "labels": t.get("labels") or [],
            "created_at": t.get("created_at"),
            "url": t.get("url"),
        })
    return out


async def list_completed_tasks(
    api_token: str,
    project_id: str,
    since: datetime,
) -> List[Dict[str, Any]]:
    """Completed tasks since `since` (UTC). Falls back to [] on API errors —
    Todoist's completed-tasks endpoint is paid/rate-limited and may 403."""
    client = TodoistClient(api_token)
    params = {
        "project_id": project_id,
        "since": since.strftime("%Y-%m-%dT%H:%M:%S"),
        "limit": 200,
    }
    res = await client._request("GET", "tasks/completed", params)
    if not res:
        return []
    items = client._extract_list(res)
    out: List[Dict[str, Any]] = []
    for t in items:
        out.append({
            "id": t.get("task_id") or t.get("id"),
            "content": t.get("content"),
            "completed_at": t.get("completed_at") or t.get("completed_date"),
        })
    return out


async def find_or_create_section(
    api_token: str,
    project_id: str,
    name: str,
) -> Optional[str]:
    """Return section_id for `name`, create if missing."""
    client = TodoistClient(api_token)
    sections = await client.get_sections(project_id)
    for s in sections:
        if (s.get("name") or "").strip().lower() == name.strip().lower():
            return s["id"]
    res = await client._request("POST", "sections", {"name": name, "project_id": project_id})
    if res:
        return res.get("id")
    return None


async def batch_execute(
    api_token: str,
    project_id: str,
    actions: List[Dict[str, Any]],
    *,
    section_today_id: Optional[str] = None,
    section_not_today_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Apply a list of actions sequentially.

    Action types:
      - create:        {service_type, client_name, quantity?, due_date, section?}
      - update:        {task_id, content?, due_date?, section?}
      - complete:      {task_id, reason}
      - delete:        {task_id, reason} (caller must validate reason length)
      - move_section:  {task_id, section}  ('Today' | 'Not Today')

    Returns: {applied: [...], failed: [{action, error}], dry_run: bool, total: N}.

    On dry_run=True every action is validated and returned as 'planned' but not
    sent to Todoist.
    """
    client = TodoistClient(api_token)
    applied: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    section_id_by_name = {
        "today": section_today_id,
        "not today": section_not_today_id,
    }

    async def _resolve_section(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        sid = section_id_by_name.get(name.strip().lower())
        if sid:
            return sid
        # Fallback: look it up / create.
        return await find_or_create_section(api_token, project_id, name)

    for action in actions:
        atype = action.get("type")
        try:
            if atype == "create":
                service = action.get("service_type") or "other"
                quantity = int(action.get("quantity") or 1)
                client_name = (action.get("client_name") or "").strip() or "—"
                service_ru = SERVICE_NAMES.get(service, service)
                content = f"{quantity} {service_ru} {client_name}" if quantity > 1 else f"{service_ru} {client_name}"
                due_date = action.get("due_date")
                section = action.get("section")
                if not section:
                    today = date.today().isoformat()
                    section = "Today" if due_date == today else "Not Today"
                section_id = await _resolve_section(section)
                if dry_run:
                    applied.append({"action": action, "result": "planned", "preview": {"content": content, "section": section, "due_date": due_date}})
                    continue
                res = await client.create_task(content=content, project_id=project_id, section_id=section_id, due_date=due_date)
                if not res:
                    raise RuntimeError("Todoist create_task returned None")
                applied.append({"action": action, "result": "created", "task_id": res.get("id"), "url": res.get("url")})

            elif atype == "update":
                task_id = action["task_id"]
                if dry_run:
                    applied.append({"action": action, "result": "planned"})
                    continue
                section_id = await _resolve_section(action.get("section")) if action.get("section") else None
                res = await client.update_task(
                    task_id,
                    content=action.get("content"),
                    due_date=action.get("due_date"),
                    section_id=section_id,
                )
                if res is None:
                    raise RuntimeError("Todoist update_task returned None")
                applied.append({"action": action, "result": "updated"})

            elif atype == "complete":
                task_id = action["task_id"]
                if dry_run:
                    applied.append({"action": action, "result": "planned"})
                    continue
                ok = await client.close_task(task_id)
                if not ok:
                    raise RuntimeError("Todoist close_task failed")
                applied.append({"action": action, "result": "completed"})

            elif atype == "delete":
                task_id = action["task_id"]
                if dry_run:
                    applied.append({"action": action, "result": "planned"})
                    continue
                ok = await client.delete_task(task_id)
                if not ok:
                    raise RuntimeError("Todoist delete_task failed")
                applied.append({"action": action, "result": "deleted"})

            elif atype == "move_section":
                task_id = action["task_id"]
                section_id = await _resolve_section(action.get("section"))
                if not section_id:
                    raise RuntimeError(f"Unknown section: {action.get('section')}")
                if dry_run:
                    applied.append({"action": action, "result": "planned"})
                    continue
                res = await client.update_task(task_id, section_id=section_id)
                if res is None:
                    raise RuntimeError("Todoist update_task(section) returned None")
                applied.append({"action": action, "result": "moved"})

            else:
                raise RuntimeError(f"Unsupported action type: {atype!r}")

        except Exception as exc:
            failed.append({"action": action, "error": f"{type(exc).__name__}: {exc}"})

    return {"applied": applied, "failed": failed, "dry_run": dry_run, "total": len(actions)}

