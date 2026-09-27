"""Guarded inserts: message dedup (§6.3) and the fenced, idempotent draft INSERT (§6.1).

Audit rows: ``app.db.audit``.
"""

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
    """Fenced, idempotent draft INSERT from the lock-holding connection (§6.1).

    Returns ``None`` (writes nothing) if a newer customer message arrived
    (``last_inbound_seq != based_on_seq``) or if this session does not hold the conversation
    lock. Otherwise returns the open draft for this seq: the new one, or, when a job is re-run
    after a crash, the one it already wrote (partial UNIQUE ``uq_draft_open_per_seq``), and moves
    ``last_processed_seq`` forward in the same transaction.

    ``FOR SHARE`` on the conversation row keeps the fence true until commit: a concurrent ingest
    that raises ``last_inbound_seq`` waits for us (and then marks this draft stale), or we wait
    for it and see the new seq. Runs in the caller's transaction on ``lock.connection``.
    """
    conn = lock.connection
    params = {"conversation_id": lock.conversation_id, "seq": based_on_seq}
    fenced = conn.execute(
        text(
            f"""
            SELECT 1 FROM conversation AS c
            WHERE c.id = :conversation_id AND c.last_inbound_seq = :seq
              AND {conversation_lock_held_here_sql()}
            FOR SHARE OF c
            """
        ),
        params,
    ).first()
    if fenced is None:
        return None
    draft_id = conn.execute(
        text(
            """
            INSERT INTO draft (conversation_id, based_on_seq, action, parts, fact_sheet,
                               prompt_version, model_id)
            VALUES (:conversation_id, :seq, :action, :parts, :fact_sheet,
                    :prompt_version, :model_id)
            ON CONFLICT (conversation_id, based_on_seq) WHERE status IN ('proposed', 'approved')
            DO NOTHING
            RETURNING id
            """
        ).bindparams(bindparam("fact_sheet", type_=JSONB)),
        {
            **params,
            "action": action,
            "parts": parts,
            "fact_sheet": fact_sheet,
            "prompt_version": prompt_version,
            "model_id": model_id,
        },
    ).scalar()
    if draft_id is None:  # replay: the open draft for this seq already exists
        draft_id = conn.execute(
            text(
                "SELECT id FROM draft WHERE conversation_id = :conversation_id "
                "AND based_on_seq = :seq AND status IN ('proposed', 'approved')"
            ),
            params,
        ).scalar_one()
    conn.execute(
        text(
            "UPDATE conversation SET last_processed_seq = :seq "
            "WHERE id = :conversation_id AND last_processed_seq < :seq"
        ),
        params,
    )
    return int(draft_id)
