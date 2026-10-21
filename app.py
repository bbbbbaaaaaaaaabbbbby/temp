import os
import uuid
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    abort,
    jsonify,
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(basedir, "app.db"),
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = os.path.join(basedir, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Сначала войдите в аккаунт."

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, default="")
    avatar_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship(
        "Post",
        backref="author",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, default="")
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref="received_messages")

    def __repr__(self):
        return f"<Message {self.sender_id} -> {self.recipient_id}>"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    if not file or not file.filename:
        return None

    original_filename = secure_filename(file.filename)

    if not original_filename or not allowed_file(original_filename):
        return None

    ext = original_filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    return filename


@app.context_processor
def inject_unread_count():
    """Делает переменную unread_messages доступной во всех шаблонах."""
    unread = 0

    if current_user.is_authenticated:
        unread = Message.query.filter_by(
            recipient_id=current_user.id,
            is_read=False
        ).count()

    return {"unread_messages": unread}


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("profile", username=current_user.username))

    return redirect(url_for("login"))


@app.route("/users")
def users():
    users_list = User.query.order_by(User.username).all()
    return render_template("users.html", users=users_list)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("profile", username=current_user.username))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            flash("Заполните обязательные поля.")
        elif len(username) < 3:
            flash("Логин должен быть не короче 3 символов.")
        elif len(password) < 6:
            flash("Пароль должен быть не короче 6 символов.")
        elif password != confirm:
            flash("Пароли не совпадают.")
        elif User.query.filter_by(username=username).first():
            flash("Такой логин уже занят.")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            flash("Регистрация прошла успешно. Теперь войдите.")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("profile", username=current_user.username))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)

            return redirect(url_for("profile", username=user.username))

        flash("Неверный логин или пароль.")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта.")
    return redirect(url_for("login"))


@app.route("/u/<username>")
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template("profile.html", user=user, posts=posts)


@app.route("/profile")
@login_required
def my_profile():
    return redirect(url_for("profile", username=current_user.username))


@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.bio = request.form.get("bio", "").strip()

        avatar = request.files.get("avatar")

        if avatar and avatar.filename:
            filename = save_upload(avatar)
            if filename:
                current_user.avatar_filename = filename
            else:
                flash("Можно загружать только изображения: png, jpg, jpeg, gif, webp.")

        db.session.commit()
        flash("Профиль обновлён.")
        return redirect(url_for("edit_profile"))

    return render_template("edit_profile.html")


@app.route("/post/create", methods=["POST"])
@login_required
def create_post():
    text = request.form.get("text", "").strip()
    image = request.files.get("image")

    image_filename = None

    if image and image.filename:
        image_filename = save_upload(image)
        if not image_filename:
            flash("Можно загружать только изображения: png, jpg, jpeg, gif, webp.")
            return redirect(url_for("profile", username=current_user.username))

    if not text and not image_filename:
        flash("Пост не может быть пустым.")
        return redirect(url_for("profile", username=current_user.username))

    post = Post(text=text, image_filename=image_filename, user_id=current_user.id)
    db.session.add(post)
    db.session.commit()

    flash("Пост опубликован.")
    return redirect(url_for("profile", username=current_user.username))


@app.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        abort(404)

    if post.user_id != current_user.id:
        abort(403)

    db.session.delete(post)
    db.session.commit()

    flash("Пост удалён.")
    return redirect(url_for("profile", username=current_user.username))


# ---------------- Личные сообщения ----------------

@app.route("/chats")
@login_required
def chats():
    my_messages = Message.query.filter(
        (Message.sender_id == current_user.id) |
        (Message.recipient_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()

    unread_counts = {}
    for message in my_messages:
        if message.recipient_id == current_user.id and not message.is_read:
            unread_counts[message.sender_id] = unread_counts.get(message.sender_id, 0) + 1

    conversations = []
    seen_partners = set()

    for message in my_messages:  # сообщения отсортированы по убыванию даты
        partner_id = (
            message.recipient_id
            if message.sender_id == current_user.id
            else message.sender_id
        )

        if partner_id in seen_partners:
            continue

        seen_partners.add(partner_id)
        partner = db.session.get(User, partner_id)

        conversations.append({
            "partner": partner,
            "last_message": message,
            "unread": unread_counts.get(partner_id, 0),
        })

    return render_template("chats.html", conversations=conversations)


@app.route("/chat/<username>")
@login_required
def chat(username):
    partner = User.query.filter_by(username=username).first_or_404()

    if partner.id == current_user.id:
        flash("Нельзя открыть чат с самим собой.")
        return redirect(url_for("chats"))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == partner.id)) |
        ((Message.sender_id == partner.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()

    # помечаем входящие как прочитанные
    updated = False
    for message in messages:
        if message.recipient_id == current_user.id and not message.is_read:
            message.is_read = True
            updated = True

    if updated:
        db.session.commit()

    return render_template("chat.html", partner=partner, messages=messages)


@app.route("/chat/<username>/send", methods=["POST"])
@login_required
def send_message(username):
    partner = User.query.filter_by(username=username).first_or_404()

    if partner.id == current_user.id:
        abort(403)

    body = request.form.get("body", "").strip()

    if not body:
        flash("Сообщение не может быть пустым.")
        return redirect(url_for("chat", username=partner.username))

    message = Message(
        body=body,
        sender_id=current_user.id,
        recipient_id=partner.id
    )

    db.session.add(message)
    db.session.commit()

    return redirect(url_for("chat", username=partner.username))


@app.route("/chat/<username>/updates")
@login_required
def chat_updates(username):
    """JSON-эндпоинт для автообновления чата."""
    partner = User.query.filter_by(username=username).first_or_404()
    after_id = request.args.get("after_id", 0, type=int)

    messages = Message.query.filter(
        Message.id > after_id,
        ((Message.sender_id == current_user.id) & (Message.recipient_id == partner.id)) |
        ((Message.sender_id == partner.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()

    updated = False
    for message in messages:
        if message.recipient_id == current_user.id and not message.is_read:
            message.is_read = True
            updated = True

    if updated:
        db.session.commit()

    return jsonify([
        {
            "id": message.id,
            "body": message.body,
            "mine": message.sender_id == current_user.id,
            "time": message.created_at.strftime("%d.%m.%Y %H:%M"),
        }
        for message in messages
    ])


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)