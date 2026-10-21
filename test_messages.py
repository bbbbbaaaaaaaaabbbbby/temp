from app import Message


def prepare_two_users(client, register, log_in):
    register("alice")
    register("bob")
    log_in("alice")


def test_send_message(client, register, log_in):
    prepare_two_users(client, register, log_in)

    response = client.post(
        "/chat/bob/send",
        data={"body": "Привет, Боб!"},
        follow_redirects=True,
    )

    page = response.get_data(as_text=True)
    assert "Привет, Боб!" in page

    message = Message.query.first()
    assert message.sender.username == "alice"
    assert message.recipient.username == "bob"
    assert message.is_read is False


def test_empty_message_not_saved(client, register, log_in):
    prepare_two_users(client, register, log_in)

    client.post("/chat/bob/send", data={"body": "   "}, follow_redirects=True)

    assert Message.query.count() == 0


def test_cannot_open_chat_with_self(auth):
    response = auth.get("/chat/alice", follow_redirects=True)

    assert "Нельзя открыть чат с самим собой" in response.get_data(as_text=True)


def test_cannot_send_message_to_self(auth):
    response = auth.post("/chat/alice/send", data={"body": "hi"})

    assert response.status_code == 403


def test_chat_page_shows_history(client, register, log_in):
    prepare_two_users(client, register, log_in)
    client.post("/chat/bob/send", data={"body": "Привет"}, follow_redirects=True)

    client.get("/logout")
    log_in("bob")
    client.post("/chat/alice/send", data={"body": "И тебе привет"}, follow_redirects=True)

    page = client.get("/chat/alice").get_data(as_text=True)

    assert "Привет" in page
    assert "И тебе привет" in page
    assert 'class="message mine"' in page
    assert 'class="message other"' in page


def test_opening_chat_marks_messages_read(client, register, log_in):
    prepare_two_users(client, register, log_in)
    client.post("/chat/bob/send", data={"body": "Привет"}, follow_redirects=True)

    client.get("/logout")
    log_in("bob")

    client.get("/chat/alice")

    assert Message.query.filter_by(is_read=False).count() == 0


def test_unread_badge_in_menu(client, register, log_in):
    prepare_two_users(client, register, log_in)
    client.post("/chat/bob/send", data={"body": "Привет"}, follow_redirects=True)

    client.get("/logout")
    log_in("bob")

    page = client.get("/", follow_redirects=True).get_data(as_text=True)
    assert '<span class="badge">1</span>' in page

    # после прочтения бейдж исчезает
    client.get("/chat/alice")
    page = client.get("/u/bob").get_data(as_text=True)
    assert 'class="badge"' not in page


def test_chats_list(client, register, log_in):
    prepare_two_users(client, register, log_in)
    client.post("/chat/bob/send", data={"body": "Последнее сообщение"}, follow_redirects=True)

    page = client.get("/chats").get_data(as_text=True)
    assert "bob" in page
    assert "Последнее сообщение" in page
    assert "Вы:" in page  # последнее сообщение — своё

    client.get("/logout")
    log_in("bob")

    page = client.get("/chats").get_data(as_text=True)
    assert "alice" in page
    assert "Вы:" not in page
    assert '<span class="badge">1</span>' in page


def test_updates_endpoint_returns_json(client, register, log_in):
    prepare_two_users(client, register, log_in)
    client.post("/chat/bob/send", data={"body": "Первое"}, follow_redirects=True)
    client.post("/chat/bob/send", data={"body": "Второе"}, follow_redirects=True)

    client.get("/logout")
    log_in("bob")

    response = client.get("/chat/alice/updates?after_id=0")

    assert response.status_code == 200
    data = response.get_json()
    assert [m["body"] for m in data] == ["Первое", "Второе"]
    assert data[0]["mine"] is False

    last_id = data[-1]["id"]
    response = client.get(f"/chat/alice/updates?after_id={last_id}")
    assert response.get_json() == []

    # входящие помечены прочитанными
    assert Message.query.filter_by(is_read=False).count() == 0