from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dmt_api.main import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)
