"""Database seeding with default data."""
from sqlalchemy.orm import Session

from app.models import Template, Tag, Setting, Admin, RejectionReason
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def seed_database(db: Session):
    """Seed database with default templates, tags, and settings."""
    
    # Seed admins from env
    seed_admins(db)
    
    # Seed default tags
    seed_tags(db)
    
    # Seed rejection reasons
    seed_rejection_reasons(db)
    
    # Seed auto-reply templates
    seed_templates(db)
    
    # Seed default settings
    seed_settings(db)

    # Seed AI-Manager digest prompts
    from app.seed_prompts import seed_prompts
    seed_prompts(db)

    # Seed reactivation templates (8 categories)
    seed_reactivation_templates(db)

    logger.info("Database seeded successfully")


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


def seed_reactivation_templates(db: Session):
    """Insert reactivation templates only if they don't exist (by category+language)."""
    from app.models import Template
    for category, language, content in REACTIVATION_TEMPLATES:
        existing = (
            db.query(Template)
            .filter(Template.category == category, Template.language == language)
            .first()
        )
        if existing:
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
    db.commit()


def seed_admins(db: Session):
    """Seed admin users from environment config."""
    settings = get_settings()
    
    for user_id in settings.admin_ids_list:
        existing = db.query(Admin).filter(Admin.telegram_user_id == user_id).first()
        if not existing:
            admin = Admin(telegram_user_id=user_id, role="owner")
            db.add(admin)
            logger.info(f"Added admin: {user_id}")
    
    db.commit()


def seed_tags(db: Session):
    """Seed default tags."""
    default_tags = [
        ("Сложный", "#ef4444"),   # Red - difficult client
        ("Повторный", "#22c55e"), # Green - returning client
    ]
    
    for name, color in default_tags:
        existing = db.query(Tag).filter(Tag.name == name).first()
        if not existing:
            tag = Tag(name=name, color=color)
            db.add(tag)
    
    db.commit()


def seed_rejection_reasons(db: Session):
    """Seed default rejection reasons."""
    defaults = [
        ("expensive", "Дорого", "💰", 1),
        ("no_prepay", "Не хочет предоплату", "💳", 2),
        ("later", "Сказал позже - не написал", "⏰", 3),
        ("competitor", "Ушёл к другому", "🔄", 4),
        ("ghosted", "Пропал без причины", "❓", 5),
        ("wrong_niche", "Не моя ниша (ошибся)", "🚫", 6),
        ("other", "Другое", "📝", 7),
    ]
    
    for code, label, emoji, order in defaults:
        existing = db.query(RejectionReason).filter(RejectionReason.code == code).first()
        if not existing:
            reason = RejectionReason(code=code, label=label, emoji=emoji, sort_order=order)
            db.add(reason)
    
    db.commit()


def seed_templates(db: Session):
    """Seed auto-reply templates."""
    templates = [
        {
            "name": "Auto-reply RU",
            "language": "ru",
            "is_auto_reply": True,
            "content": """Привет, {first_name}! 👋

Спасибо за сообщение! Я отвечу вам в ближайшее время.

Пока жду ответа, расскажите:
• Какая у вас задача?
• Какие сроки?

Портфолио: {portfolio_url}"""
        },
        {
            "name": "Auto-reply EN",
            "language": "en",
            "is_auto_reply": True,
            "content": """Hi {first_name}! 👋

Thanks for reaching out! I'll get back to you shortly.

While I'm reviewing your message, could you share:
• What's your project about?
• What's your timeline?

Portfolio: {portfolio_url}"""
        },
        {
            "name": "Auto-reply UA",
            "language": "ua",
            "is_auto_reply": True,
            "content": """Привіт, {first_name}! 👋

Дякую за повідомлення! Відповім найближчим часом.

Поки чекаю, розкажіть:
• Яке у вас завдання?
• Які терміни?

Портфоліо: {portfolio_url}"""
        },
        {
            "name": "Auto-reply ES",
            "language": "es",
            "is_auto_reply": True,
            "content": """¡Hola {first_name}! 👋

¡Gracias por escribir! Te responderé pronto.

Mientras tanto, cuéntame:
• ¿Cuál es tu proyecto?
• ¿Cuál es tu plazo?

Portafolio: {portfolio_url}"""
        },
        {
            "name": "Quick: Follow up RU",
            "language": "ru",
            "is_auto_reply": False,
            "content": """Привет! Хотел уточнить — удалось ли вам принять решение по проекту?

Буду рад помочь, если остались вопросы."""
        },
        {
            "name": "Quick: Follow up EN",
            "language": "en",
            "is_auto_reply": False,
            "content": """Hi! Just wanted to follow up — have you had a chance to make a decision on the project?

Happy to help if you have any questions."""
        },
    ]
    
    for tpl_data in templates:
        existing = db.query(Template).filter(
            Template.name == tpl_data["name"],
            Template.language == tpl_data["language"],
        ).first()
        
        if not existing:
            template = Template(**tpl_data)
            db.add(template)
    
    db.commit()


def seed_settings(db: Session):
    """Seed default settings."""
    settings = get_settings()
    
    defaults = {
        "portfolio_url": settings.portfolio_url,
        "auto_reply_enabled": "true" if settings.auto_reply_enabled else "false",
        "social_proof": "100+ completed projects",
    }
    
    for key, value in defaults.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if not existing:
            setting = Setting(key=key, value=value)
            db.add(setting)
    
    db.commit()
