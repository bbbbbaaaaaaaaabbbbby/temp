import io
import os

from app import User, app as flask_app


def test_profile_shows_username_and_bio(auth):
    user = User.query.filter_by(username="alice").first()
    user.bio = "Привет, я Алиса"
    from app import db
    db.session.commit()

    page = auth.get("/u/alice").get_data(as_text=True)

    assert "alice" in page
    assert "Привет, я Алиса" in page


def test_profile_404_for_unknown_user(client):
    assert client.get("/u/nobody").status_code == 404


def test_users_list_shows_everyone(client, register):
    register("alice")
    register("bob")

    page = client.get("/users").get_data(as_text=True)

    assert "alice" in page
    assert "bob" in page


def test_foreign_profile_has_message_button(client, register, log_in):
    register("alice")
    register("bob")
    log_in("alice")

    page = client.get("/u/bob").get_data(as_text=True)

    assert "Написать сообщение" in page
    assert 'href="/chat/bob"' in page


def test_own_profile_has_edit_button(auth):
    page = auth.get("/u/alice").get_data(as_text=True)

    assert "Редактировать профиль" in page
    assert "Написать сообщение" not in page


def test_edit_profile_updates_bio(auth):
    response = auth.post(
        "/edit-profile",
        data={"bio": "Новое описание"},
        follow_redirects=True,
    )

    assert "Профиль обновлён" in response.get_data(as_text=True)

    user = User.query.filter_by(username="alice").first()
    assert user.bio == "Новое описание"


def test_edit_profile_avatar_upload(auth):
    response = auth.post(
        "/edit-profile",
        data={
            "bio": "",
            "avatar": (io.BytesIO(b"fake-png-bytes"), "avatar.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    user = User.query.filter_by(username="alice").first()

    assert user.avatar_filename is not None
    assert user.avatar_filename.endswith(".png")

    path = os.path.join(flask_app.config["UPLOAD_FOLDER"], user.avatar_filename)
    assert os.path.exists(path)


def test_uploaded_avatar_is_served(auth):
    auth.post(
        "/edit-profile",
        data={
            "bio": "",
            "avatar": (io.BytesIO(b"fake-png-bytes"), "avatar.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    user = User.query.filter_by(username="alice").first()
    response = auth.get(f"/uploads/{user.avatar_filename}")

    assert response.status_code == 200
    assert response.data == b"fake-png-bytes"


def test_edit_profile_rejects_bad_extension(auth):
    response = auth.post(
        "/edit-profile",
        data={
            "bio": "",
            "avatar": (io.BytesIO(b"not-an-image"), "virus.exe"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert "Можно загружать только изображения" in response.get_data(as_text=True)

    user = User.query.filter_by(username="alice").first()
    assert user.avatar_filename is None