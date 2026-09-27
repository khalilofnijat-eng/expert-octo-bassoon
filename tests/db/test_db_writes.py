# SYNTHETIC: chats, message ids and texts are made up.
"""Message dedup and ordering, fenced idempotent draft INSERT, CAS, intent CAS, settings changes
with the outbox group rule, schema CHECKs, and append-only audit on real PostgreSQL."""

from __future__ import annotations

import threading
import time
import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from app.db.audit import append_audit
from app.db.cas import cas_update, claim_send_intent
from app.db.models import Conversation, Draft
from app.db.settings import (
    force_kill_switch_after_restore,
    set_automation_mode,
    set_kill_switch,
)
from app.db.writes import insert_draft_fenced, record_message
from app.queue.locks import SingletonToken, conversation_lock
from tests.db.factories import (
    customer_message,
    enable_sending,
    make_conversation,
    make_draft,
    make_outbound,
)


def _scalar(engine: Engine, sql: str, **params: object) -> object:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def test_message_dedup_on_avito_message_id(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    assert customer_message(engine, cid, "SYN-m1") == 1
    assert customer_message(engine, cid, "SYN-m1") is None  # webhook + poller: one row
    assert customer_message(engine, cid, "SYN-m2") == 2
    assert _scalar(engine, "SELECT count(*) FROM message") == 2
    assert _scalar(engine, "SELECT last_inbound_seq FROM conversation") == 2


def test_parallel_record_message_gap_free_seq(engine: Engine) -> None:
    """Concurrent ingest for one conversation: no duplicate seq, no lost message."""
    with engine.begin() as conn:
        cid = make_conversation(conn)
    errors: list[str] = []
    barrier = threading.Barrier(8)

    def ingest(worker: int) -> None:
        barrier.wait()
        for i in range(5):
            try:
                customer_message(engine, cid, f"SYN-{worker}-{i}")
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(repr(exc))

    threads = [threading.Thread(target=ingest, args=(w,)) for w in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with engine.connect() as conn:
        seqs = sorted(conn.execute(text("SELECT seq FROM message")).scalars())
    assert seqs == list(range(1, 41))
    assert _scalar(engine, "SELECT last_inbound_seq FROM conversation") == 40


def test_draft_insert_fenced_on_seq_and_lock(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    customer_message(engine, cid, "SYN-m1")
    with conversation_lock(engine, cid) as lock:
        assert lock is not None
        with lock.connection.begin():
            ok = insert_draft_fenced(lock, based_on_seq=1, action="ask_info", parts=["SYN a"])
        assert ok is not None
        customer_message(engine, cid, "SYN-m2")  # new message while the draft was being made
        with lock.connection.begin():
            stale = insert_draft_fenced(lock, based_on_seq=1, action="ask_info", parts=["SYN b"])
        assert stale is None
    # A handle whose session no longer holds the lock cannot write either.
    with conversation_lock(engine, cid) as lock:
        assert lock is not None
        lock.connection.execute(text("SELECT pg_advisory_unlock_all()"))
        lock.connection.commit()
        with lock.connection.begin():
            assert insert_draft_fenced(lock, based_on_seq=2, action="a", parts=["SYN c"]) is None
    assert _scalar(engine, "SELECT count(*) FROM draft") == 1
    assert _scalar(engine, "SELECT last_processed_seq FROM conversation") == 1


def test_draft_insert_is_idempotent_per_seq(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    customer_message(engine, cid, "SYN-m1")
    with conversation_lock(engine, cid) as lock:
        assert lock is not None
        with lock.connection.begin():
            first = insert_draft_fenced(lock, based_on_seq=1, action="a", parts=["SYN a"])
        with lock.connection.begin():  # the same job re-run after a crash
            again = insert_draft_fenced(lock, based_on_seq=1, action="a", parts=["SYN a2"])
    assert first is not None and again == first
    assert _scalar(engine, "SELECT count(*) FROM draft") == 1
    with engine.begin() as conn, pytest.raises(IntegrityError):
        make_draft(conn, cid, 1)  # partial UNIQUE: one open draft per seq


def test_draft_insert_waits_for_concurrent_ingest(engine: Engine) -> None:
    """E7: an ingest transaction (new customer message + marking open drafts stale) is in flight
    when the draft is written. FOR SHARE makes the draft see the new seq: no stale open draft."""
    with engine.begin() as conn:
        cid = make_conversation(conn)
    customer_message(engine, cid, "SYN-m1")
    with engine.connect() as ingest:
        ingest.begin()
        record_message(
            ingest,
            conversation_id=cid,
            avito_message_id="SYN-m2",
            author_role="customer",
            direction="in",
            type="text",
            source="webhook",
        )
        ingest.execute(
            text(
                "UPDATE draft SET status = 'stale' "
                "WHERE conversation_id = :c AND status = 'proposed'"
            ),
            {"c": cid},
        )
        result: dict[str, object] = {}

        def write_draft() -> None:
            with conversation_lock(engine, cid) as lock:
                assert lock is not None
                started = time.monotonic()
                with lock.connection.begin():
                    result["draft"] = insert_draft_fenced(
                        lock, based_on_seq=1, action="a", parts=["SYN"]
                    )
                result["waited"] = time.monotonic() - started

        t = threading.Thread(target=write_draft)
        t.start()
        t.join(0.5)
        assert t.is_alive()  # waiting on the ingest's row lock
        ingest.commit()
        t.join(5)
    assert result["draft"] is None
    assert (
        _scalar(
            engine,
            "SELECT count(*) FROM draft d JOIN conversation c ON c.id = d.conversation_id "
            "WHERE d.status = 'proposed' AND d.based_on_seq < c.last_inbound_seq",
        )
        == 0
    )


def test_cas_conflict_second_writer_loses(engine: Engine) -> None:
    with engine.begin() as conn:
        draft = make_draft(conn, make_conversation(conn), 0)
    with engine.begin() as conn:
        assert cas_update(
            conn,
            Draft,
            draft,
            expected_status="proposed",
            expected_version=0,
            values={"status": "approved"},
        )
    with engine.begin() as conn:
        assert not cas_update(
            conn,
            Draft,
            draft,
            expected_status="proposed",
            expected_version=0,
            values={"status": "rejected"},
        )
        assert not cas_update(
            conn,
            Draft,
            draft,
            expected_status="approved",
            expected_version=0,
            values={"status": "stale"},
        )
        status, version = conn.execute(
            text("SELECT status, version FROM draft WHERE id = :i"), {"i": draft}
        ).one()
    assert (status, version) == ("approved", 1)


def test_cas_race_exactly_one_winner(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    wins: list[bool] = []
    barrier = threading.Barrier(8)

    def attempt(target: str) -> None:
        barrier.wait()
        with engine.begin() as conn:
            wins.append(
                cas_update(
                    conn,
                    Conversation,
                    cid,
                    expected_status="new_request",
                    expected_version=0,
                    values={"state": target},
                    status_column="state",
                    version_column="state_version",
                )
            )

    threads = [
        threading.Thread(target=attempt, args=(s,)) for s in ["awaiting_info", "researching"] * 4
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(wins) == [False] * 7 + [True]


def _intent_setup(engine: Engine, part_count: int = 2) -> tuple[int, int, list[int]]:
    with engine.begin() as conn:
        enable_sending(conn)
        cid = make_conversation(conn)
    customer_message(engine, cid, "SYN-m1")
    with engine.begin() as conn:
        draft = make_draft(conn, cid, 1)
        parts = [make_outbound(conn, draft, n, part_count) for n in range(1, part_count + 1)]
    return cid, draft, parts


def _intent(engine: Engine, outbound: int, token: SingletonToken, version: int = 0) -> bool:
    with engine.begin() as conn:
        return claim_send_intent(conn, outbound, version, token)


def _mark_sent(engine: Engine, outbound: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE outbound_message SET status = 'sent' WHERE id = :i"), {"i": outbound}
        )


def test_intent_cas_happy_path_and_part_order(engine: Engine, token: SingletonToken) -> None:
    cid, _, (part1, part2) = _intent_setup(engine)
    assert not _intent(engine, part2, token)  # part 2 before part 1 is sent
    assert _intent(engine, part1, token)
    assert not _intent(engine, part1, token)  # version moved: second CAS fails
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, attempts, intent_at IS NOT NULL AS has_intent "
                "FROM outbound_message WHERE id = :i"
            ),
            {"i": part1},
        ).one()
    assert tuple(row) == ("sending", 1, True)
    _mark_sent(engine, part1)
    customer_message(engine, cid, "SYN-m2")  # a new message after part 1 does not stop part 2
    assert _intent(engine, part2, token)


def test_intent_cas_rejects_stale_seq(engine: Engine, token: SingletonToken) -> None:
    cid, _, (part1, _) = _intent_setup(engine)
    customer_message(engine, cid, "SYN-m2")
    assert not _intent(engine, part1, token)


def test_intent_cas_rejects_kill_switch(engine: Engine, token: SingletonToken) -> None:
    _, _, (part1, _) = _intent_setup(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE system_setting SET kill_switch = true"))
    assert not _intent(engine, part1, token)
    with engine.begin() as conn:
        conn.execute(text("UPDATE system_setting SET kill_switch = false"))
    assert _intent(engine, part1, token)


def test_intent_cas_rejects_draft_only_mode_for_every_part(
    engine: Engine, token: SingletonToken
) -> None:
    _, _, (part1, part2) = _intent_setup(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE system_setting SET automation_mode = 'draft_only'"))
    assert not _intent(engine, part1, token)
    _mark_sent(engine, part1)  # even with part 1 out, part 2 may not go in draft_only
    assert not _intent(engine, part2, token)


def test_intent_cas_rejects_missing_settings_row(engine: Engine, token: SingletonToken) -> None:
    _, _, (part1, _) = _intent_setup(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM system_setting"))
    assert not _intent(engine, part1, token)


def test_intent_cas_rejects_paused_automation(engine: Engine, token: SingletonToken) -> None:
    cid, _, (part1, _) = _intent_setup(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE conversation SET automation = 'paused', paused_reason = 'owner_takeover', "
                "paused_at = now() WHERE id = :c"
            ),
            {"c": cid},
        )
    assert not _intent(engine, part1, token)


def test_intent_cas_rejects_without_singleton(engine: Engine, token: SingletonToken) -> None:
    _, _, (part1, _) = _intent_setup(engine)
    with engine.connect() as conn:
        other_pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
    assert not _intent(engine, part1, SingletonToken(other_pid, token.epoch))  # not the holder
    assert not _intent(engine, part1, SingletonToken(token.pid, token.epoch - 1))  # old epoch
    assert _intent(engine, part1, token)


def _statuses(engine: Engine) -> dict[int, str]:
    with engine.connect() as conn:
        return {
            r.id: r.status for r in conn.execute(text("SELECT id, status FROM outbound_message"))
        }


def _automation(engine: Engine, cid: int) -> tuple[str, str | None]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT automation, paused_reason FROM conversation WHERE id = :c"), {"c": cid}
        ).one()
    return row.automation, row.paused_reason


def _setting_version(engine: Engine) -> int:
    return int(str(_scalar(engine, "SELECT version FROM system_setting")))


def test_kill_switch_on_applies_group_rule(engine: Engine, token: SingletonToken) -> None:
    started_cid, _, (s1, s2) = _intent_setup(engine)
    assert _intent(engine, s1, token)  # group A has started
    with engine.begin() as conn:
        idle_cid = make_conversation(conn, "SYN-chat-2")
        idle = make_outbound(conn, make_draft(conn, idle_cid, 0), 1, 1)  # group B has not
    with engine.begin() as conn:
        assert not set_kill_switch(conn, True, expected_version=99, actor="owner")  # CAS
        assert set_kill_switch(conn, True, expected_version=_setting_version(engine), actor="owner")
    assert _statuses(engine) == {s1: "sending", s2: "cancelled", idle: "cancelled"}
    assert _automation(engine, started_cid) == ("paused", "group_incomplete")
    assert _automation(engine, idle_cid) == ("active", None)


def test_mode_change_to_draft_only_applies_group_rule(
    engine: Engine, token: SingletonToken
) -> None:
    cid, _, (p1, p2) = _intent_setup(engine)
    assert _intent(engine, p1, token)
    _mark_sent(engine, p1)
    with engine.begin() as conn:
        assert set_automation_mode(
            conn, "draft_only", expected_version=_setting_version(engine), actor="owner"
        )
    assert _statuses(engine) == {p1: "sent", p2: "cancelled"}
    assert _automation(engine, cid) == ("paused", "group_incomplete")
    assert not _intent(engine, p2, token, version=1)


def test_restore_forces_kill_switch(engine: Engine) -> None:
    with engine.begin() as conn:
        enable_sending(conn)
        force_kill_switch_after_restore(conn)
    assert _scalar(engine, "SELECT kill_switch FROM system_setting") is True
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM system_setting"))
        force_kill_switch_after_restore(conn)  # recreates the row, switch on
    assert _scalar(engine, "SELECT kill_switch FROM system_setting") is True


@pytest.mark.parametrize(
    "values",
    [
        {"automation": "paused"},  # paused needs a reason
        {"paused_reason": "made_up_reason"},
        {"state": "closed"},  # closed needs a close reason
        {"close_reason": "inactive"},  # a close reason only when closed
    ],
)
def test_conversation_checks(engine: Engine, values: dict[str, str]) -> None:
    with engine.begin() as conn, pytest.raises(IntegrityError):
        make_conversation(conn, "SYN-chat-check", **values)


def test_conversation_checks_accept_consistent_rows(engine: Engine) -> None:
    with engine.begin() as conn:
        make_conversation(conn, "SYN-a", automation="paused", paused_reason="llm_outage")
        make_conversation(conn, "SYN-b", state="closed", close_reason="owner_closed")


def test_audit_append_only_for_owner_and_app_role(engine: Engine) -> None:
    op_id = f"SYN-op-{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        append_audit(
            conn,
            op_id=op_id,
            actor="worker",
            action="draft_created",
            result="ok",
            entity_ids={"draft_id": 1},
        )
    # Owner / superuser: the trigger refuses UPDATE, DELETE and TRUNCATE while enabled.
    for stmt in (
        "UPDATE audit_event SET result = 'x' WHERE op_id = :o",
        "DELETE FROM audit_event WHERE op_id = :o",
        "TRUNCATE audit_event",
    ):
        with engine.begin() as conn, pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text(stmt), {"o": op_id})
    # Runtime role: INSERT allowed; UPDATE/DELETE and disabling the trigger refused.
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE assistant_app"))
        append_audit(conn, op_id=op_id, actor="worker", action="second", result="ok")
    for stmt in (
        "UPDATE audit_event SET result = 'x' WHERE op_id = :o",
        "DELETE FROM audit_event WHERE op_id = :o",
        "ALTER TABLE audit_event DISABLE TRIGGER USER",
    ):
        with (
            engine.begin() as conn,
            pytest.raises(ProgrammingError, match=r"permission denied|must be owner"),
        ):
            conn.execute(text("SET LOCAL ROLE assistant_app"))
            conn.execute(text(stmt), {"o": op_id})
    count = _scalar(engine, "SELECT count(*) FROM audit_event WHERE op_id = :o", o=op_id)
    assert count == 2
