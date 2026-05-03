"""One-shot: classify existing rejected Conversations into normalized categories.

Default dry-run. Pass `apply=True` (CLI: --apply) to mutate.

For each Conversation where status='rejected' AND rejection_normalized_category IS NULL:
  1. Build context: rejection_reason code + rejection_custom + last 10 messages
  2. Call rejection_classifier (Groq + JSON mode)
  3. UPDATE: normalized_category, confidence, classified_at
  4. Throttle 100ms between LLM calls
"""
import argparse
import asyncio
from typing import Dict

from sqlalchemy import desc

from app.db import SessionLocal
from app.llm.rejection_classifier import classify_rejection
from app.models import Conversation, Message
from app.utils.timezone import now_georgia


THROTTLE_MS = 100


async def cleanup_or_classify(apply: bool) -> Dict[str, int]:
    db = SessionLocal()
    try:
        targets = (
            db.query(Conversation)
            .filter(Conversation.status == "rejected")
            .filter(Conversation.rejection_normalized_category.is_(None))
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        counts: Dict[str, int] = {}
        total = len(targets)
        if total == 0:
            print("No rejected conversations need classification.")
            return counts
        print(f"{'APPLYING' if apply else 'DRY-RUN'} on {total} rejected conversations…\n")

        for i, conv in enumerate(targets, 1):
            msgs = (
                db.query(Message)
                .filter(Message.conversation_id == conv.id)
                .order_by(desc(Message.sent_at))
                .limit(10)
                .all()
            )
            msgs.reverse()
            context = "\n".join(
                f"{'OUT' if m.direction == 'out' else 'IN'}: {(m.transcription if m.message_type == 'voice' else m.text) or ''}"
                for m in msgs
            )
            raw = (conv.rejection_custom or conv.rejection_reason or "")
            try:
                category, confidence = await classify_rejection(raw, context, db)
            except Exception as exc:
                print(f"  [{i}/{total}] conv #{conv.id}: ERROR {type(exc).__name__}: {exc}")
                category, confidence = ("other", 0.0)
            counts[category] = counts.get(category, 0) + 1
            print(f"  [{i}/{total}] conv #{conv.id} client={conv.client_id} → {category} ({confidence:.2f})  raw={raw[:60]!r}")
            if apply:
                conv.rejection_normalized_category = category
                conv.rejection_classification_confidence = confidence
                conv.rejection_classified_at = now_georgia()
            await asyncio.sleep(THROTTLE_MS / 1000)

        if apply:
            db.commit()

        print()
        print(f"{'APPLIED' if apply else 'DRY-RUN'} done.")
        for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            pct = round(100 * n / total, 1)
            print(f"  {cat:20s}  {n:>4}  ({pct}%)")
        return counts
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(cleanup_or_classify(apply=args.apply))


if __name__ == "__main__":
    main()
