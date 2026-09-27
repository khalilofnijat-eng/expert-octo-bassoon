"""Append-only audit rows (AGENTS.md §7): ids and codes only. There is no update or delete.

Alerts (e.g. a job that went ``dead``) are audit rows with ``result = 'alert'``; the health and
notifier work (T-029) reads them from here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.expression import bindparam

_INSERT = text(
    """
    INSERT INTO audit_event (op_id, correlation_id, actor, action, entity_ids,
                             reason_code, reason_short, result)
    VALUES (:op_id, :correlation_id, :actor, :action, :entity_ids,
            :reason_code, :reason_short, :result)
    RETURNING id
    """
).bindparams(bindparam("entity_ids", type_=JSONB))


def append_audit(
    conn: Connection,
    *,
    op_id: str,
    actor: str,
    action: str,
    result: str,
    entity_ids: dict[str, Any] | None = None,
    reason_code: str | None = None,
    reason_short: str | None = None,
    correlation_id: str | None = None,
) -> int:
    """Append one audit row in the caller's transaction."""
    return int(
        conn.execute(
            _INSERT,
            {
                "op_id": op_id,
                "correlation_id": correlation_id,
                "actor": actor,
                "action": action,
                "entity_ids": entity_ids or {},
                "reason_code": reason_code,
                "reason_short": reason_short,
                "result": result,
            },
        ).scalar_one()
    )


def new_op_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex}"


def record_alert(
    conn: Connection, *, action: str, entity_ids: dict[str, Any], reason_code: str | None
) -> int:
    """Append an alert row (``result = 'alert'``) for the owner-facing alert band (§6.11)."""
    return append_audit(
        conn,
        op_id=new_op_id(action),
        actor="system",
        action=action,
        result="alert",
        entity_ids=entity_ids,
        reason_code=reason_code,
    )
