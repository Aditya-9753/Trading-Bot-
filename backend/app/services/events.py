"""Notifications (DB + WebSocket push) and audit logging."""
from sqlalchemy.orm import Session

from ..models import AuditLog, Notification
from .realtime import hub


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "") -> Notification:
    n = Notification(user_id=user_id, kind=kind, title=title[:160], body=body[:500])
    db.add(n)
    db.flush()
    hub.publish({"type": "notification", "data": {"id": n.id, "kind": kind, "title": n.title, "body": n.body}},
                user_id=user_id)
    return n


def audit(db: Session, user_id: int | None, action: str, target: str = "", detail: dict | None = None,
          ip: str = "") -> None:
    db.add(AuditLog(user_id=user_id, action=action, target=target[:120], detail=detail, ip=ip[:45]))
