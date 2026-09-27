# SYNTHETIC: fixtures load the made-up W213 dataset only.
from __future__ import annotations

import pytest

from app.catalog.dataset import SyntheticDataset, load_synthetic_dataset
from app.catalog.evidence import EvidencePolicy
from app.catalog.runtime import RuntimeMode


@pytest.fixture(scope="session")
def dataset() -> SyntheticDataset:
    return load_synthetic_dataset()


@pytest.fixture
def test_policy() -> EvidencePolicy:
    return EvidencePolicy(RuntimeMode.TEST)
