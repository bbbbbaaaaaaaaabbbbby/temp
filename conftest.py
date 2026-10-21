import os
import pathlib
import shutil
import tempfile

import pytest

# ВАЖНО: задаём переменную окружения ДО импорта app,
# чтобы приложение сразу использовало тестовую базу,
# а не настоящий app.db.
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "flask_social_test.db"

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB_PATH.as_posix()

from app import app, db  # noqa: E402


@pytest.fixture
def client():
    """Тестовый клиент с чистой БД и временной папкой uploads."""
    upload_dir = tempfile.mkdtemp()
    old_upload_folder = app.config["UPLOAD_FOLDER"]

    app.config.update(
        TESTING=True,
        UPLOAD_FOLDER=upload_dir,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

        yield app.test_client()

        db.session.remove()

    app.config["UPLOAD_FOLDER"] = old_upload_folder
    shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture
def register(client):
    """Регистрирует пользователя."""
    def _register(username, password="password123", confirm=None):
        return client.post(
            "/register",
            data={
                "username": username,
                "password": password,
                "confirm": confirm if confirm is not None else password,
            },
            follow_redirects=True,
        )
    return _register


@pytest.fixture
def log_in(client):
    """Входит в систему."""
    def _log_in(username, password="password123"):
        return client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )
    return _log_in


@pytest.fixture
def auth(client, register, log_in):
    """Клиент, зарегистрированный и вошедший как alice."""
    register("alice")
    log_in("alice")
    return client