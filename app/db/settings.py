"""``system_setting`` changes: kill switch, automation mode, and the post-restore hook.

The DB row is the single source of truth (the ``AUTOMATION_MODE`` environment value only seeds it
in the first migration). Every change is a CAS on ``version`` and writes an audit row (§5).

Whenever sending stops (kill switch on, or a mode that does not send), the outbox group rule
(§4.5, §6.13) runs at once: every ``pending`` part is cancelled; a group whose part 1 had already
started cannot finish, so its conversation becomes ``paused(group_incomplete)``. Rows already in
``sending`` are left alone (one in-flight request may still complete, §6.13).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, text

from app.db.audit import append_audit, new_op_id

# Modes in which the outbox may send (intent CAS allowlist, app.db.cas).
SENDING_MODES = ("approve_to_send",)


@dataclass(frozen=True)
class StopResult:
    cancelled_parts: int
    paused_conversations: int


def stop_open_outbox_groups(conn: Connection) -> StopResult:
    """Apply the group rule for a stop (kill switch, non-sending mode, restore)."""
    row = conn.execute(
        text(
            """
            WITH started AS (
                SELECT DISTINCT draft_id, generation FROM outbound_message
                WHERE status IN ('sending', 'sent', 'unknown', 'needs_owner', 'failed')
            ), cancelled AS (
                UPDATE outbound_message SET status = 'cancelled', version = version + 1
                WHERE status = 'pending'
                RETURNING draft_id, generation
            ), broken AS (
                SELECT DISTINCT d.conversation_id
                FROM cancelled AS x
                JOIN started AS s USING (draft_id, generation)
                JOIN draft AS d ON d.id = x.draft_id
            ), paused AS (
                UPDATE conversation AS c
                SET automation = 'paused', paused_reason = 'group_incomplete', paused_at = now(),
                    state_version = c.state_version + 1
                FROM broken AS b
                WHERE c.id = b.conversation_id AND c.automation = 'active'
                RETURNING c.id
            )
            SELECT (SELECT count(*) FROM cancelled) AS cancelled,
                   (SELECT count(*) FROM paused) AS paused
            """
        )
    ).one()
    return StopResult(int(row.cancelled), int(row.paused))


def _change(
    conn: Connection, column: str, value: object, expected_version: int, actor: str
) -> bool:
    changed = conn.execute(
        text(
            f"UPDATE system_setting SET {column} = :value, version = version + 1 "
            "WHERE id = 1 AND version = :v"
        ),
        {"value": value, "v": expected_version},
    )
    if changed.rowcount != 1:
        return False
    append_audit(
        conn,
        op_id=new_op_id(f"set_{column}"),
        actor=actor,
        action=f"set_{column}",
        entity_ids={"system_setting": 1, column: value},
        result="ok",
    )
    return True


def set_kill_switch(conn: Connection, on: bool, *, expected_version: int, actor: str) -> bool:
    """CAS the kill switch. Turning it on stops open outbox groups; turning it off sends nothing
    by itself (§6.13)."""
    if not _change(conn, "kill_switch", on, expected_version, actor):
        return False
    if on:
        stop_open_outbox_groups(conn)
    return True


def set_automation_mode(conn: Connection, mode: str, *, expected_version: int, actor: str) -> bool:
    """CAS the automation mode. A mode that does not send stops open outbox groups."""
    if not _change(conn, "automation_mode", mode, expected_version, actor):
        return False
    if mode not in SENDING_MODES:
        stop_open_outbox_groups(conn)
    return True


def force_kill_switch_after_restore(conn: Connection, *, actor: str = "restore") -> StopResult:
    """Restore hook (§6.8, T-031): unconditionally turn the kill switch on and stop open outbox
    groups. Call it right after a backup is restored, before the worker starts."""
    conn.execute(
        text(
            "INSERT INTO system_setting (id, kill_switch) VALUES (1, true) ON CONFLICT (id) "
            "DO UPDATE SET kill_switch = true, version = system_setting.version + 1"
        )
    )
    stopped = stop_open_outbox_groups(conn)
    append_audit(
        conn,
        op_id=new_op_id("restore_kill_switch"),
        actor=actor,
        action="restore_kill_switch",
        entity_ids={"system_setting": 1},
        result="ok",
    )
    return stopped
