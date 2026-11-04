import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="forja_test_"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp / 'test.db'}",
    "CELERY_TASK_ALWAYS_EAGER": "true",
    "STORAGE_DIR": str(_tmp / "storage"),
    "TEMP_DIR": str(_tmp / "tmp"),
    "LLM_PROVIDER": "template",
    "IMAGE_PROVIDER": "procedural",
    "TTS_PROVIDER": os.environ.get("TEST_TTS_PROVIDER", "espeak"),
    "SECRET_KEY": "test-secret-key-0123456789-abcdefghijkl",
    "ALLOW_REGISTRATION": "true",
    "LOGIN_MAX_ATTEMPTS": "1000",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.templates import seed_templates  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_templates(db)
    db.close()
    yield


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _register(client, email, name="Teste"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "Senha12345"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _register(client, "admin@example.com", "Admin")


@pytest.fixture(scope="session")
def user_headers(client, admin_headers):
    return _register(client, "user@example.com", "Usuário")


@pytest.fixture(scope="session")
def other_headers(client, admin_headers):
    return _register(client, "other@example.com", "Outro")
