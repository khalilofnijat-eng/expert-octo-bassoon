"""Runtime mode for the catalog and inventory code: ``production``, ``development`` or ``test``.

The mode decides how synthetic data is treated (docs/ARCHITECTURE.md §3, T-022):

- ``test``: synthetic fixtures and ``synthetic_fixture`` evidence are accepted, and every result
  that used them is flagged ``synthetic``.
- ``development``: the synthetic inventory adapter may run, but ``synthetic_fixture`` evidence
  never counts as verification (such parts stay ``needs_verification``).
- ``production``: the synthetic adapter refuses to start and any synthetic evidence or synthetic
  record reaching the fitment engine raises ``SyntheticDataRejected``.

The mode is read from ``APP_ENV``. It is read here and not in ``app.config`` because that module
belongs to another task; see the T-022 report. **Fail-safe default:** an unset or unknown value
means ``production``, so synthetic data is refused unless someone explicitly opts in.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum

APP_ENV_VARIABLE = "APP_ENV"


class RuntimeMode(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"


class SyntheticDataRejected(RuntimeError):
    """Synthetic data or synthetic evidence was offered in a mode that must not use it."""


def current_runtime_mode(environ: Mapping[str, str] | None = None) -> RuntimeMode:
    """Return the mode named by ``APP_ENV``; unset, empty or unknown values mean production."""
    env = os.environ if environ is None else environ
    raw = (env.get(APP_ENV_VARIABLE) or "").strip().lower()
    try:
        return RuntimeMode(raw)
    except ValueError:
        return RuntimeMode.PRODUCTION
