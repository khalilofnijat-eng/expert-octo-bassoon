"""Guarded inserts: message dedup (§6.3), the fenced draft INSERT (§6.1) and audit append."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.expression import bindparam

from app.queue.locks import ConversationLock, conversation_lock_held_here_sql


def record_message(
    conn: Connection,
    *,
    conversation_id: int,
    avito_message_id: str,
    author_role: str,
    direction: str,
    type: str,
    source: str,
    content_masked: str | None = None,
    author_avito_id: str | None = None,
    created_at_avito: datetime | None = None,
) -> int | None:
    """Insert a message once per ``avito_message_id`` (webhook, poller and import share this).

    Returns the new ``seq`` or ``None`` for a duplicate. A customer message moves
    ``conversation.last_inbound_seq``, which makes older drafts stale (§6.4). The conversation row
    is locked first so seq numbers are gap-free and ordered per conversation.
    """
    conn.execute(
        text("SELECT 1 FROM conversation WHERE id = :cid FOR UPDATE"), {"cid": conversation_id}
    )
    seq = conn.execute(
        text(
            """
            INSERT INTO message (avito_message_id, conversation_id, seq, author_role,
                author_avito_id, direction, type, created_at_avito, content_masked, source)
            SELECT :mid, :cid,
                   COALESCE((SELECT max(seq) FROM message WHERE conversation_id = :cid), 0) + 1,
                   :role, :author, :direction, :type, :created, :content, :source
            ON CONFLICT (avito_message_id) DO NOTHING
            RETURNING seq
            """
        ),
        {
            "mid": avito_message_id,
            "cid": conversation_id,
            "role": author_role,
            "author": author_avito_id,
            "direction": direction,
            "type": type,
            "created": created_at_avito,
            "content": content_masked,
            "source": source,
        },
    ).scalar()
    if seq is not None and author_role == "customer":
        conn.execute(
            text("UPDATE conversation SET last_inbound_seq = :seq WHERE id = :cid"),
            {"seq": seq, "cid": conversation_id},
        )
    return None if seq is None else int(seq)


def insert_draft_fenced(
    lock: ConversationLock,
    *,
    based_on_seq: int,
    action: str,
    parts: list[str],
    fact_sheet: dict[str, Any] | None = None,
    prompt_version: str | None = None,
    model_id: str | None = None,
) -> int | None:
    """Conditional draft INSERT from the lock-holding connection (§6.1 write-time fencing).

    Inserts nothing (returns ``None``) if a newer customer message arrived
    (``last_inbound_seq != based_on_seq``) or if this session no longer holds the conversation
    lock. ``FOR SHARE`` makes a concurrent seq update wait for us, or makes us re-check the new
    seq, so a stale draft cannot slip in between. Runs in the caller's transaction on
    ``lock.connection``.
    """
    row = lock.connection.execute(
        text(
            f"""
            INSERT INTO draft (conversation_id, based_on_seq, action, parts, fact_sheet,
                               prompt_version, model_id)
            SELECT c.id, :seq, :action, :parts, :fact_sheet, :prompt_version, :model_id
            FROM conversation AS c
            WHERE c.id = :conversation_id AND c.last_inbound_seq = :seq
              AND {conversation_lock_held_here_sql()}
            FOR SHARE OF c
            RETURNING id
            """
        ).bindparams(bindparam("fact_sheet", type_=JSONB)),
        {
            "conversation_id": lock.conversation_id,
            "seq": based_on_seq,
            "action": action,
            "parts": parts,
            "fact_sheet": fact_sheet,
            "prompt_version": prompt_version,
            "model_id": model_id,
        },
    ).scalar()
    return None if row is None else int(row)


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
    """Append one audit row (ids and codes only, AGENTS.md §7). There is no update or delete."""
    return int(
        conn.execute(
            text(
                """
                INSERT INTO audit_event (op_id, correlation_id, actor, action, entity_ids,
                                         reason_code, reason_short, result)
                VALUES (:op_id, :correlation_id, :actor, :action, :entity_ids,
                        :reason_code, :reason_short, :result)
                RETURNING id
                """
            ).bindparams(bindparam("entity_ids", type_=JSONB)),
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
