from werkzeug.security import check_password_hash

from app import User


def test_register_page_opens(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert "Регистрация" in response.get_data(as_text=True)


def test_register_success(client, register):
    response = register("alice")
    page = response.get_data(as_text=True)

    assert "Регистрация прошла успешно" in page
    assert User.query.filter_by(username="alice").first() is not None


def test_register_stores_hashed_password(client, register):
    register("alice")
    user = User.query.filter_by(username="alice").first()

    assert user.password_hash != "password123"
    assert check_password_hash(user.password_hash, "password123")


def test_register_duplicate_username(client, register):
    register("alice")
    response = register("alice")

    assert "логин уже занят" in response.get_data(as_text=True)
    assert User.query.count() == 1


def test_register_password_mismatch(client, register):
    response = register("alice", confirm="another123")

    assert "Пароли не совпадают" in response.get_data(as_text=True)
    assert User.query.count() == 0


def test_register_short_password(client, register):
    response = register("alice", password="123")

    assert "не короче 6" in response.get_data(as_text=True)
    assert User.query.count() == 0


def test_login_success(client, register, log_in):
    register("alice")
    response = log_in("alice")

    assert "alice" in response.get_data(as_text=True)

    with client.session_transaction() as session:
        assert "_user_id" in session


def test_login_wrong_password(client, register, log_in):
    register("alice")
    response = log_in("alice", password="wrongpass")

    assert "Неверный логин или пароль" in response.get_data(as_text=True)

    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_logout(auth):
    response = auth.get("/logout", follow_redirects=True)

    assert "Вы вышли из аккаунта" in response.get_data(as_text=True)

    with auth.session_transaction() as session:
        assert "_user_id" not in session


def test_protected_page_requires_login(client):
    response = client.get("/edit-profile")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]