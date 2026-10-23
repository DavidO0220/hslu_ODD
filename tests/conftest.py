import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_test_model import build  # noqa: E402

MODEL_PATH = ROOT / "data" / "testmodell.ifc"


@pytest.fixture(scope="session")
def model_path() -> Path:
    """Erzeugt das Testmodell, falls es noch nicht existiert."""
    if not MODEL_PATH.exists():
        build(MODEL_PATH)
    return MODEL_PATH


@pytest.fixture(scope="session")
def model(model_path):
    from core.ifc_reader import load_model_from_path
    return load_model_from_path(model_path)
