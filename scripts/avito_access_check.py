"""Read-only Avito access check (T-039). Run: ``uv run python scripts/avito_access_check.py``.

Makes at most four calls, each once, and never retries:

(a) ``POST /token`` (client_credentials; issues a token, changes nothing on Avito)
(b) ``GET /core/v1/accounts/self``
(c) ``GET /core/v1/items`` with ``per_page=1``
(d) ``GET /messenger/v2/accounts/{user_id}/chats`` with ``limit=1`` (read-only per the spec copy;
    ``chatRead`` is never called and is not on the gateway allowlist)

It prints statuses only, in Turkish: no tokens, no chat ids, no message contents, and only the
last three digits of the account id. It uses the gateway read client with
``refresh_on_401=False``, ``Priority.BULK`` and ``silence_httpx_url_logs()``.

``--dry-run`` talks to the in-process synthetic mock (``AvitoMock(...).transport()``) and never
touches the network or the configured credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

if __package__ in (None, ""):
    # ``python scripts/avito_access_check.py`` puts scripts/ on sys.path, not the repo root.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.avito_gateway import (
    AvitoApiError,
    AvitoAuthError,
    AvitoClientError,
    AvitoNetworkError,
    AvitoRateLimitedError,
    AvitoReadClient,
    AvitoServerError,
    AvitoTimeoutError,
    AvitoUnexpectedPayloadError,
    Credentials,
    GatewayConfig,
    MissingCredentialsError,
    Priority,
)
from app.avito_gateway.http import silence_httpx_url_logs
from app.config import SecretsFileError, Settings, resolve_secrets_file

T = TypeVar("T")

EXIT_OK = 0
EXIT_ACCESS_PROBLEM = 1
EXIT_CONFIG_PROBLEM = 2

MESSENGER_403_HINT = "403 → muhtemelen tarife kısıtı (hangi tarifenin gerektiği canlı doğrulanmadı)"
DRY_RUN_SCENARIOS = ("ok", "messenger-403", "token-401")


@dataclass(frozen=True)
class StepResult:
    """Outcome of one call. ``failure`` is a short Turkish failure class (None when ok)."""

    ok: bool
    status: int | None = None
    failure: str | None = None
    skipped: bool = False


@dataclass
class AccessReport:
    token: StepResult
    account: StepResult | None = None
    account_id_tail: str | None = None
    # True/False when AVITO_USER_ID is set and accounts/self answered; None otherwise.
    configured_id_matches: bool | None = None
    items: StepResult | None = None
    messenger: StepResult | None = None

    @property
    def all_ok(self) -> bool:
        return all(
            step is not None and step.ok
            for step in (self.token, self.account, self.items, self.messenger)
        )


def failure_class(exc: BaseException) -> str:
    """A short Turkish description of an error (without the status). Never contains values."""
    if isinstance(exc, AvitoRateLimitedError):
        return "hız sınırı — birkaç dakika sonra tekrar deneyin"
    if isinstance(exc, AvitoAuthError):
        return "yetki reddedildi"
    if isinstance(exc, AvitoServerError):
        return "Avito sunucu hatası — daha sonra tekrar deneyin"
    if isinstance(exc, AvitoTimeoutError):
        return "zaman aşımı — internet bağlantısını kontrol edin"
    if isinstance(exc, AvitoNetworkError):
        return "ağ hatası — internet bağlantısını / güvenlik duvarını kontrol edin"
    if isinstance(exc, AvitoUnexpectedPayloadError):
        return "beklenmeyen yanıt biçimi"
    if isinstance(exc, AvitoClientError):
        return "istek reddedildi"
    return f"beklenmeyen hata ({type(exc).__name__})"


async def _step(call: Callable[[], Awaitable[T]]) -> tuple[StepResult, T | None]:
    try:
        value = await call()
    except AvitoApiError as exc:
        return StepResult(ok=False, status=exc.status, failure=failure_class(exc)), None
    # Token replies are not exposed with their status; a token only exists after a 2xx.
    status = getattr(value, "status", 200)
    return StepResult(ok=True, status=status if isinstance(status, int) else 200), value


async def run_access_check(
    client: AvitoReadClient, *, configured_user_id: int | None = None
) -> AccessReport:
    """The four calls, in order, each at most once. Stops after a failed token request."""
    token, _ = await _step(client.tokens.get)
    report = AccessReport(token=token)
    if not token.ok:
        return report

    account, me = await _step(lambda: client.get_self(priority=Priority.BULK))
    report.account = account
    if me is not None:
        report.account_id_tail = str(me.data.id)[-3:]
        if configured_user_id is not None:
            report.configured_id_matches = configured_user_id == me.data.id
    user_id = me.data.id if me is not None else configured_user_id

    items, _ = await _step(lambda: client.list_items(per_page=1, priority=Priority.BULK))
    report.items = items

    if user_id is None:
        report.messenger = StepResult(ok=False, skipped=True, failure="hesap kimliği yok")
    else:
        uid = user_id
        messenger, _ = await _step(lambda: client.list_chats(uid, limit=1, priority=Priority.BULK))
        report.messenger = messenger
    return report


def _http(step: StepResult) -> str:
    return f"HTTP {step.status}" if step.status is not None else "yanıt yok"


def _yes_no(step: StepResult) -> str:
    if step.skipped:
        return f"denenmedi ({step.failure})"
    if step.ok:
        return f"evet ({_http(step)})"
    return f"hayır ({_http(step)}; {step.failure})"


def format_report(report: AccessReport, *, dry_run: bool) -> list[str]:
    lines: list[str] = []
    if dry_run:
        lines.append(
            "KURU ÇALIŞTIRMA — sentetik mock; Avito'ya bağlanılmadı; sonuçlar gerçek değil."
        )
    token = report.token
    if token.ok:
        lines.append("Token: OK")
    else:
        lines.append(f"Token: BAŞARISIZ ({_http(token)}) — {token.failure}")
        if token.status in (400, 401, 403):
            lines.append(
                "  İpucu: client_id / client_secret yanlış veya iptal edilmiş olabilir; "
                "kurulum betiğini yeniden çalıştırın."
            )
        lines.append("Diğer kontroller yapılmadı.")
        return lines

    account = report.account
    if account is not None and account.ok and report.account_id_tail is not None:
        lines.append(f"Hesap kimliği: bulundu (son 3 hane …{report.account_id_tail})")
    elif account is not None:
        lines.append(f"Hesap kimliği: alınamadı ({_http(account)}; {account.failure})")
        if report.messenger is not None and not report.messenger.skipped:
            lines.append("  Messenger kontrolü ayarlardaki AVITO_USER_ID ile yapıldı.")
    if report.configured_id_matches is True:
        lines.append("AVITO_USER_ID: ayarlı ve API'nin döndürdüğü kimlikle aynı")
    elif report.configured_id_matches is False:
        lines.append(
            "AVITO_USER_ID: ayarlı ama API'nin döndürdüğü kimlikle AYNI DEĞİL — "
            "kurulum betiğinde hesap kimliğini boş bırakmayı veya düzeltmeyi düşünün"
        )

    if report.items is not None:
        lines.append(f"Items API erişilebilir: {_yes_no(report.items)}")
    messenger = report.messenger
    if messenger is not None:
        lines.append(f"Messenger API erişilebilir: {_yes_no(messenger)}")
        if messenger.status == 403:
            lines.append(f"  Yorum: {MESSENGER_403_HINT}")
    lines.append("Bu çıktı gizli değer içermez; Main Agent'a iletebilirsiniz.")
    return lines


def _dry_run_client(scenario: str) -> AvitoReadClient:
    from scripts.dev.avito_mock import AvitoMock, config_for_mock, forbidden, unauthorized

    mock = AvitoMock.with_synthetic_data(n_chats=2, messages_per_chat=2, n_items=2)
    if scenario == "messenger-403":
        mock.inject(forbidden(), endpoint="chats_list")
    elif scenario == "token-401":
        mock.inject(unauthorized(), endpoint="token")
    return AvitoReadClient(
        config_for_mock(refresh_on_401=False), mock.credentials(), transport=mock.transport()
    )


async def _run(client: AvitoReadClient, configured_user_id: int | None) -> AccessReport:
    async with client:
        return await run_access_check(client, configured_user_id=configured_user_id)


def _configure_output(verbose: bool) -> None:
    # Never crash on a console code page that cannot show a character (e.g. Cyrillic).
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")
    silence_httpx_url_logs()
    # Gateway log lines hold endpoint names and statuses only, never ids or tokens; they are
    # still noise for the owner, so they are shown only with --verbose.
    logging.basicConfig(level=logging.INFO if verbose else logging.ERROR, stream=sys.stderr)
    if not verbose:
        logging.getLogger("app.avito_gateway").setLevel(logging.ERROR)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Avito API erişim kontrolü (salt okunur, en fazla 4 istek)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Avito yerine sentetik mock ile çalıştır (ağ yok, kimlik bilgisi okunmaz).",
    )
    parser.add_argument(
        "--scenario",
        choices=DRY_RUN_SCENARIOS,
        default="ok",
        help="Yalnızca --dry-run ile: örnek senaryo (çıktının nasıl okunacağını görmek için).",
    )
    parser.add_argument("--verbose", action="store_true", help="İstek günlüklerini de göster.")
    args = parser.parse_args(argv)
    _configure_output(args.verbose)

    if args.dry_run:
        report = asyncio.run(_run(_dry_run_client(args.scenario), None))
    else:
        if args.scenario != "ok":
            parser.error("--scenario yalnızca --dry-run ile kullanılır")
        try:
            settings = Settings()
            secrets_file = resolve_secrets_file(settings.assistant_secrets_file)
            credentials = Credentials.from_settings(settings)
        except SecretsFileError as exc:
            print(f"Ayar hatası: gizli dosya kullanılamıyor ({exc}).")
            return EXIT_CONFIG_PROBLEM
        except MissingCredentialsError:
            print(
                "Ayar hatası: AVITO_CLIENT_ID / AVITO_CLIENT_SECRET ayarlı değil. "
                "Önce scripts/windows/setup-avito-credentials.ps1 betiğini çalıştırın."
            )
            return EXIT_CONFIG_PROBLEM
        except ValidationError as exc:
            # Only field names: a ValidationError's text would include the input values.
            fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
            print(f"Ayar hatası: geçersiz değer ({', '.join(fields) or 'bilinmiyor'}).")
            return EXIT_CONFIG_PROBLEM
        print(f"Gizli dosya: {'bulundu' if secrets_file is not None else 'yok (ortam/.env)'}")
        try:
            config = GatewayConfig(refresh_on_401=False)
        except ValidationError as exc:
            fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
            print(f"Ayar hatası: AVITO_GATEWAY_* geçersiz ({', '.join(fields) or 'genel'}).")
            return EXIT_CONFIG_PROBLEM
        client = AvitoReadClient(config, credentials)
        report = asyncio.run(_run(client, settings.avito_user_id))

    for line in format_report(report, dry_run=args.dry_run):
        print(line)
    return EXIT_OK if report.all_ok else EXIT_ACCESS_PROBLEM


if __name__ == "__main__":
    raise SystemExit(main())
