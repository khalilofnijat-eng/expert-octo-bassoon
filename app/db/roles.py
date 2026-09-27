"""Runtime role check (ARCHITECTURE §5 audit_event, T-035 decision on roles).

The application connects as its own LOGIN role that is a member of ``assistant_app`` and never
the table owner: the owner can disable the append-only trigger on ``audit_event``. Migrations run
as the owner. In production the worker refuses to start if the connected role could act as the
owner of ``audit_event`` (or is a superuser).
"""

from __future__ import annotations

from sqlalchemy import Connection, text

from app.config import AppEnv


class UnsafeDatabaseRoleError(RuntimeError):
    """The application is connected as a role that can bypass the audit protections."""


def check_runtime_role(conn: Connection, app_env: AppEnv) -> None:
    """Raise ``UnsafeDatabaseRoleError`` in production if ``current_user`` owns ``audit_event``
    (directly or through membership) or is a superuser. Other environments only check nothing."""
    if app_env is not AppEnv.PRODUCTION:
        return
    row = conn.execute(
        text(
            """
            SELECT r.rolsuper
                OR pg_has_role(current_user, c.relowner, 'MEMBER')
                OR pg_has_role(current_user, c.relowner, 'USAGE') AS unsafe,
                   current_user AS who
            FROM pg_class AS c, pg_roles AS r
            WHERE c.oid = 'audit_event'::regclass AND r.rolname = current_user
            """
        )
    ).one()
    if row.unsafe:
        raise UnsafeDatabaseRoleError(
            f"database role {row.who!r} owns audit_event or is a superuser; in production the "
            "application must connect as a member of assistant_app (app/README.md)"
        )
