"""One-shot cleanup of pending Orders that point to dead Todoist tasks.

Flow per Order with status='pending' AND todoist_task_id IS NOT NULL:
  1. Look up the task in Todoist.
  2. Task active           → leave it alone.
  3. Task completed        → mark Order completed (use task.completed_at if known).
  4. Task missing (404)    → look at last 15 client messages and ask Groq
                             "судя по сообщениям, заказ {service_type} от {date}
                              похоже на закрытый?". YES/NO/UNCLEAR.
                             - YES → status='completed'
                             - NO/UNCLEAR + клиент молчит ≥14 дней → 'cancelled'
                             - NO/UNCLEAR + клиент пишет недавно → leave (in flight).

Run:
    python -m app.scripts.cleanup_orphan_orders                  # dry-run
    python -m app.scripts.cleanup_orphan_orders --apply          # apply

Output: per-order classification + summary counts.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc

from app.crud import get_setting
from app.db import SessionLocal
from app.integrations.todoist import TodoistClient
from app.llm.llm_client import _groq_completion
from app.models import Message, Order
from app.utils.timezone import now_georgia

SILENT_DAYS_FOR_CANCEL = 14


def _service_ru_name(s: str) -> str:
    return {
        "thumbnail": "превью", "banner": "баннер", "logo": "лого",
        "channel_design": "оформление канала", "avatar": "аватар",
        "cover": "обложка", "template": "шаблоны", "other": "что-то",
    }.get(s, s)


async def _ask_llm_is_closed(messages: list[Message], service_type: str, created_at: datetime) -> str:
    """Returns 'YES' | 'NO' | 'UNCLEAR'."""
    if not messages:
        return "UNCLEAR"
    convo = "\n".join(
        f"{'OUT' if m.direction == 'out' else 'IN'} [{m.sent_at:%Y-%m-%d}]: {(m.text or '')[:300]}"
        for m in messages
    )
    prompt = (
        "Ты анализируешь переписку фрилансера-дизайнера с клиентом.\n"
        f"Заказ: {_service_ru_name(service_type)} от {created_at:%Y-%m-%d}.\n"
        "Вопрос: судя по сообщениям, этот заказ был закрыт (сдан клиенту, оплачен, "
        "клиент сказал спасибо/одобрил)?\n\n"
        "Ответ строго JSON: {\"closed\": \"YES\" | \"NO\" | \"UNCLEAR\", \"reason\": \"коротко\"}.\n\n"
        "Переписка (последние сообщения):\n" + convo
    )
    raw = await _groq_completion(
        [{"role": "system", "content": "Ты выдаёшь только JSON."},
         {"role": "user", "content": prompt}],
        max_completion_tokens=200,
        temperature=0.0,
    )
    if not raw:
        return "UNCLEAR"
    try:
        # Strip markdown fences if any
        text = raw.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        data = json.loads(text)
        val = (data.get("closed") or "").upper()
        return val if val in {"YES", "NO", "UNCLEAR"} else "UNCLEAR"
    except Exception:
        return "UNCLEAR"


async def cleanup(apply: bool) -> dict:
    db = SessionLocal()
    try:
        api_token = get_setting(db, "todoist_api_token")
        project_id = get_setting(db, "todoist_project_id")
        if not api_token or not project_id:
            print("ERROR: Todoist not configured (api_token / project_id missing).", file=sys.stderr)
            return {"error": "no todoist config"}

        tc = TodoistClient(api_token)
        active = await tc.get_tasks(project_id=project_id)
        active_ids = {t["id"] for t in active}
        # Completed in the last 60 days — covers most realistic cases.
        completed_since = now_georgia() - timedelta(days=60)
        completed_resp = await tc._request("GET", "tasks/completed", {
            "project_id": project_id,
            "since": completed_since.strftime("%Y-%m-%dT%H:%M:%S"),
            "limit": 500,
        })
        completed_items = tc._extract_list(completed_resp) if completed_resp else []
        completed_index = {(c.get("task_id") or c.get("id")): c for c in completed_items}

        orders = (
            db.query(Order)
            .filter(Order.status == "pending")
            .filter(Order.todoist_task_id.isnot(None))
            .all()
        )

        plan = {"completed_via_todoist": [], "completed_via_ai": [],
                "cancelled": [], "left_alone": [], "skipped_no_messages": []}

        now = now_georgia()
        for o in orders:
            decision = None
            note_suffix = None

            if o.todoist_task_id in active_ids:
                decision = "left_alone"
                note_suffix = "todoist task still active"
            elif o.todoist_task_id in completed_index:
                ci = completed_index[o.todoist_task_id]
                completed_at_raw = ci.get("completed_at") or ci.get("completed_date")
                decision = "completed_via_todoist"
                note_suffix = f"auto-closed: Todoist task completed at {completed_at_raw}"
                target_completed_at = _parse_iso(completed_at_raw) or now
            else:
                # Task missing → ask AI from messages
                msgs = (
                    db.query(Message)
                    .filter(Message.client_id == o.client_id)
                    .order_by(desc(Message.sent_at))
                    .limit(15)
                    .all()
                )
                if not msgs:
                    decision = "skipped_no_messages"
                    note_suffix = "no messages to infer"
                else:
                    msgs_chrono = list(reversed(msgs))
                    verdict = await _ask_llm_is_closed(msgs_chrono, o.service_type, o.created_at or now)
                    last_msg_at = max(m.sent_at for m in msgs)
                    silent_days = (now - last_msg_at).days if last_msg_at else 999

                    if verdict == "YES":
                        decision = "completed_via_ai"
                        note_suffix = "auto-closed: AI inferred completion from messages"
                        target_completed_at = now
                    elif silent_days >= SILENT_DAYS_FOR_CANCEL:
                        decision = "cancelled"
                        note_suffix = f"todoist task missing, no completion signal, silent {silent_days}d"
                    else:
                        decision = "left_alone"
                        note_suffix = f"todoist task missing but client active ({silent_days}d silent)"

            entry = {
                "order_id": o.id, "client_id": o.client_id,
                "service_type": o.service_type, "todoist_task_id": o.todoist_task_id,
                "note_suffix": note_suffix,
            }
            plan[decision].append(entry)

            if apply:
                if decision == "completed_via_todoist":
                    o.status = "completed"
                    o.completed_at = target_completed_at  # type: ignore[name-defined]
                    o.notes = (o.notes or "") + f"\n[cleanup] {note_suffix}"
                elif decision == "completed_via_ai":
                    o.status = "completed"
                    o.completed_at = target_completed_at  # type: ignore[name-defined]
                    o.notes = (o.notes or "") + f"\n[cleanup] {note_suffix}"
                elif decision == "cancelled":
                    o.status = "cancelled"
                    o.notes = (o.notes or "") + f"\n[cleanup] {note_suffix}"

        if apply:
            db.commit()

        # Print human report
        print(f"\n{'APPLIED' if apply else 'DRY-RUN'} — orphan orders cleanup")
        print(f"Total candidates: {sum(len(v) for v in plan.values())}\n")
        for k, items in plan.items():
            print(f"  {k}: {len(items)}")
        print()
        for k in ("completed_via_todoist", "completed_via_ai", "cancelled"):
            if not plan[k]:
                continue
            print(f"\n=== {k} ===")
            for e in plan[k][:50]:
                print(f"  Order #{e['order_id']} ({e['service_type']}) client={e['client_id']} → {e['note_suffix']}")
        print()
        return {k: len(v) for k, v in plan.items()}
    finally:
        db.close()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually mutate the DB. Default is dry-run.")
    args = parser.parse_args()
    asyncio.run(cleanup(apply=args.apply))


if __name__ == "__main__":
    main()
