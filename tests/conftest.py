"""Fixture autouse que aísla cada test de cualquier ORACLE_* de entorno.

El repo trae un .env real (gitignoreado) que config.py carga al importar.
Para que los tests sean deterministas limpiamos ORACLE_*/OX_* por test.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def clean_oracle_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("ORACLE_") or name.startswith("OX_"):
            monkeypatch.delenv(name, raising=False)
    yield
