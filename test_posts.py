from app import Post, User


def test_create_post(auth):
    response = auth.post(
        "/post/create",
        data={"text": "Первый пост"},
        follow_redirects=True,
    )

    assert "Пост опубликован" in response.get_data(as_text=True)

    post = Post.query.first()
    alice = User.query.filter_by(username="alice").first()

    assert post.text == "Первый пост"
    assert post.user_id == alice.id


def test_create_empty_post_rejected(auth):
    auth.post("/post/create", data={"text": "   "}, follow_redirects=True)

    assert Post.query.count() == 0


def test_post_appears_on_wall(auth):
    auth.post("/post/create", data={"text": "Запись на стене"}, follow_redirects=True)

    page = auth.get("/u/alice").get_data(as_text=True)

    assert "Запись на стене" in page


def test_delete_own_post(auth):
    auth.post("/post/create", data={"text": "Удали меня"}, follow_redirects=True)
    post = Post.query.first()

    response = auth.post(f"/post/{post.id}/delete", follow_redirects=True)

    assert "Пост удалён" in response.get_data(as_text=True)
    assert Post.query.count() == 0


def test_cannot_delete_foreign_post(client, register, log_in):
    register("alice")
    register("bob")
    log_in("alice")

    client.post("/post/create", data={"text": "Пост Алисы"}, follow_redirects=True)

    client.get("/logout")
    log_in("bob")

    post = Post.query.first()
    response = client.post(f"/post/{post.id}/delete")

    assert response.status_code == 403
    assert Post.query.count() == 1