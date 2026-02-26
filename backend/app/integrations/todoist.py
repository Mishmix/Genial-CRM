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
    
    async def get_projects(self) -> List[Dict]:
        """Get all projects"""
        result = await self._request("GET", "projects")
        return result if result else []
    
    async def get_sections(self, project_id: str) -> List[Dict]:
        """Get all sections for a project"""
        result = await self._request("GET", "sections", {"project_id": project_id})
        return result if result else []
    
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
    
    async def get_tasks(self, project_id: Optional[str] = None) -> List[Dict]:
        """Get active tasks"""
        params = {}
        if project_id:
            params["project_id"] = project_id
        
        result = await self._request("GET", "tasks", params)
        return result if result else []
    
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
