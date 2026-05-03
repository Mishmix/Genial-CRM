"""Admin / one-shot operations callable via routine token.

Currently exposes the orphan-orders cleanup that previously could only be run
through `python -m app.scripts.cleanup_orphan_orders` (which requires Railway
shell access).
"""
import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.api.routes_digest import require_routine_token
from app.db import get_db
from app.scripts.cleanup_orphan_orders import cleanup
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/admin/cleanup-orphan-orders", dependencies=[Depends(require_routine_token)])
async def admin_cleanup_orphan_orders(apply: bool = Query(False)):
    """Run the orphan-orders cleanup script. Default is dry-run."""
    counts = await cleanup(apply=apply)
    return {"applied": apply, "counts": counts}


@router.post("/admin/classify-rejections", dependencies=[Depends(require_routine_token)])
async def admin_classify_rejections(apply: bool = Query(False)):
    """Backfill `Conversation.rejection_normalized_category` for old rejected
    conversations. Default dry-run; ?apply=true mutates."""
    from app.scripts.classify_existing_rejections import cleanup_or_classify
    counts = await cleanup_or_classify(apply=apply)
    return {"applied": apply, "counts": counts}


REACTIVATION_TEMPLATES = [
    ("reactivation_too_expensive", "ru",
     "Привет, {first_name}! Делаю даунселл-вариант обложки за 50% обычного прайса — для своих. Если актуально — могу сегодня прислать"),
    ("reactivation_no_urgency", "ru",
     "Привет, {first_name}! Видел канал растёт — обычно как раз в этой стадии нужны новые обложки под алгоритм. Готов под тебя слот следующая неделя?"),
    ("reactivation_chose_competitor", "ru",
     "Привет, {first_name}! Как зашло сотрудничество? Если хочешь сравнить — могу сделать тестовую обложку бесплатно, посмотришь разницу"),
    ("reactivation_ghosting", "ru",
     "Привет, {first_name}! Хотел уточнить — актуально ещё или закрываем?"),
    ("reactivation_value_unclear", "ru",
     "Привет, {first_name}! Покажу пару кейсов где обложка дала +30% CTR за неделю — посмотришь?"),
    ("reactivation_no_budget", "ru",
     "Привет, {first_name}! Есть мысль — могу сделать одну тестовую обложку бесплатно, если зайдёт — продолжим. Интересно?"),
    ("reactivation_scope_mismatch", "ru",
     "Привет, {first_name}! У меня тут расширили услуги — теперь делаем и баннеры/оформление. Если что-то из этого подходит — пиши"),
    ("reactivation_timing_mismatch", "ru",
     "Привет, {first_name}! Прошло время — сейчас как раз могу взять. Актуально ещё?"),
]


@router.post("/admin/seed-reactivation-templates", dependencies=[Depends(require_routine_token)])
async def admin_seed_reactivation_templates(db=Depends(get_db)):
    """Lazy-seed 8 reactivation Templates. Idempotent: skips existing rows.

    Lives outside startup intentionally — startup must stay thin.
    """
    from app.models import Template
    created = []
    skipped = []
    for category, language, content in REACTIVATION_TEMPLATES:
        existing = (
            db.query(Template)
            .filter(Template.category == category, Template.language == language)
            .first()
        )
        if existing:
            skipped.append(category)
            continue
        name = category.replace("reactivation_", "").replace("_", " ").title()
        db.add(Template(
            name=f"Реактивация: {name}",
            language=language,
            content=content,
            is_auto_reply=False,
            category=category,
            is_active=True,
        ))
        created.append(category)
    db.commit()
    return {"created": created, "skipped": skipped}


@router.get("/admin/reactivation-candidates")
async def admin_reactivation_candidates(db=Depends(get_db), _user: dict = Depends(get_current_user)):
    """Same detector as morning digest, exposed for the Mini App's ReactivationPage."""
    from app.services.rejection_reactivation import detect_reactivation_candidates
    from app.utils.timezone import now_georgia
    return await detect_reactivation_candidates(db, now_georgia(), top_n=200)


@router.post("/reactivation/mark-attempt")
async def mark_reactivation_attempt(
    payload: Dict[str, Any] = Body(...),
    db=Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Increment reactivation_attempts on a Conversation. Called from Mini App."""
    from app.models import Conversation
    from app.utils.timezone import now_georgia
    conv_id = payload.get("conversation_id")
    if not conv_id:
        raise HTTPException(status_code=400, detail="conversation_id required")
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.reactivation_attempts = (conv.reactivation_attempts or 0) + 1
    conv.last_reactivation_at = now_georgia()
    db.commit()
    return {
        "ok": True,
        "conversation_id": conv.id,
        "reactivation_attempts": conv.reactivation_attempts,
        "last_reactivation_at": conv.last_reactivation_at.isoformat(),
    }


@router.get("/admin/detectors-smoke", dependencies=[Depends(require_routine_token)])
async def admin_detectors_smoke(db=Depends(get_db)):
    """Run all 3 v4 detectors and return raw output. PR#2 smoke endpoint.

    Each detector is wrapped — failure in one returns its error rather than
    crashing the whole call. Detectors are not yet wired into /digest/data.
    """
    from app.utils.timezone import now_georgia
    now = now_georgia()
    out: Dict[str, Any] = {}
    try:
        from app.services.money_at_risk import detect_money_at_risk
        out["money_at_risk"] = await detect_money_at_risk(db, now)
    except Exception as exc:
        out["money_at_risk_error"] = f"{type(exc).__name__}: {exc}"
    try:
        from app.services.predictive_reorders import detect_predictive_reorders
        out["predictive_reorders"] = await detect_predictive_reorders(db, now)
    except Exception as exc:
        out["predictive_reorders_error"] = f"{type(exc).__name__}: {exc}"
    try:
        from app.services.rejection_reactivation import detect_reactivation_candidates
        out["rejection_reactivation"] = await detect_reactivation_candidates(db, now)
    except Exception as exc:
        out["rejection_reactivation_error"] = f"{type(exc).__name__}: {exc}"
    return out
