from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from comic_service import ComicService
import os
from urllib.parse import urlencode

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-this-for-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"

# Authentication and AWS environment configuration
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN", "").rstrip("/")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET", "")
COGNITO_REGION = os.getenv("COGNITO_REGION", os.getenv("AWS_REGION", "us-east-1"))
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
POST_LOGOUT_REDIRECT_URI = os.getenv("POST_LOGOUT_REDIRECT_URI", "")

cognito_configured = all([
    COGNITO_DOMAIN,
    COGNITO_CLIENT_ID,
    COGNITO_CLIENT_SECRET,
    COGNITO_USER_POOL_ID,
    COGNITO_REGION,
])

oauth = OAuth(app)
if cognito_configured:
    oauth.register(
        name="cognito",
        client_id=COGNITO_CLIENT_ID,
        client_secret=COGNITO_CLIENT_SECRET,
        api_base_url=COGNITO_DOMAIN,
        authorize_url=f"{COGNITO_DOMAIN}/oauth2/authorize",
        access_token_url=f"{COGNITO_DOMAIN}/oauth2/token",
        userinfo_endpoint=f"{COGNITO_DOMAIN}/oauth2/userInfo",
        client_kwargs={"scope": "openid email profile"},
    )

# Initialize the comic service
comic_service = ComicService()


def _is_api_request() -> bool:
    return request.path.startswith("/api/")


def _is_public_endpoint(endpoint: str) -> bool:
    return endpoint in {"login", "auth_callback", "static", "health"}


@app.before_request
def require_authentication():
    if not AUTH_REQUIRED:
        return None

    endpoint = request.endpoint or ""
    if _is_public_endpoint(endpoint):
        return None

    if session.get("user"):
        return None

    if _is_api_request():
        return jsonify({"error": "authentication required"}), 401

    session["next_url"] = request.url
    return redirect(url_for("login"))


@app.context_processor
def inject_user_context():
    return {
        "auth_required": AUTH_REQUIRED,
        "is_authenticated": bool(session.get("user")),
        "current_user": session.get("user", {}),
    }


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/login")
def login():
    if not AUTH_REQUIRED:
        return redirect(url_for("index"))

    if not cognito_configured:
        flash("Cognito is not configured. Set Cognito environment variables.", "error")
        return render_template("login.html"), 500

    redirect_uri = url_for("auth_callback", _external=True)
    next_url = request.args.get("next")
    if next_url:
        session["next_url"] = next_url
    return oauth.cognito.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    if not cognito_configured:
        return redirect(url_for("login"))

    token = oauth.cognito.authorize_access_token()
    userinfo = oauth.cognito.userinfo(token=token) or {}

    session["user"] = {
        "sub": userinfo.get("sub"),
        "email": userinfo.get("email"),
        "name": userinfo.get("name") or userinfo.get("email") or "User",
    }

    next_url = session.pop("next_url", None)
    return redirect(next_url or url_for("index"))


@app.route("/logout")
def logout():
    session.clear()

    if not cognito_configured:
        return redirect(url_for("login"))

    logout_target = POST_LOGOUT_REDIRECT_URI or url_for("login", _external=True)
    query = urlencode({
        "client_id": COGNITO_CLIENT_ID,
        "logout_uri": logout_target,
    })
    return redirect(f"{COGNITO_DOMAIN}/logout?{query}")


@app.route('/')
def index():
    """Main page showing all comics"""
    sort_by = request.args.get('sort', 'title')
    sort_order = request.args.get('order', 'asc')
    page = int(request.args.get('page', 1))
    per_page = 50

    comics = comic_service.get_all_comics()

    if sort_by == 'title':
        comics.sort(key=lambda x: x.title.lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'writer':
        comics.sort(key=lambda x: x.writer.lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'artist':
        comics.sort(key=lambda x: x.artist.lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'volume':
        comics.sort(key=lambda x: int(x.volume) if x.volume.isdigit() else 0, reverse=(sort_order == 'desc'))

    total_comics = len(comics)
    total_pages = (total_comics + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_comics = comics[start_idx:end_idx]

    has_prev = page > 1
    has_next = page < total_pages
    prev_page = page - 1 if has_prev else None
    next_page = page + 1 if has_next else None

    return render_template(
        'index.html',
        comics=paginated_comics,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        total_pages=total_pages,
        total_comics=total_comics,
        has_prev=has_prev,
        has_next=has_next,
        prev_page=prev_page,
        next_page=next_page,
        per_page=per_page,
    )


@app.route('/add', methods=['GET', 'POST'])
def add_comic():
    """Add a new comic"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        volume = request.form.get('volume', '').strip()
        writer = request.form.get('writer', '').strip()
        artist = request.form.get('artist', '').strip()

        if not all([title, volume, writer, artist]):
            flash('All fields are required!', 'error')
            return render_template('add_comic.html')

        try:
            comic_service.add_comic(title, volume, writer, artist)
            flash(f'Comic "{title}" added successfully!', 'success')
            return redirect(url_for('index'))
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('add_comic.html')

    return render_template('add_comic.html')


@app.route('/add-multiple', methods=['GET', 'POST'])
def add_multiple_comics():
    """Add multiple comics at once"""
    if request.method == 'POST':
        comics_data = []

        i = 0
        while True:
            title = request.form.get(f'title_{i}', '').strip()
            volume = request.form.get(f'volume_{i}', '').strip()
            writer = request.form.get(f'writer_{i}', '').strip()
            artist = request.form.get(f'artist_{i}', '').strip()

            if not title:
                break

            if all([title, volume, writer, artist]):
                comics_data.append({
                    'title': title,
                    'volume': volume,
                    'writer': writer,
                    'artist': artist,
                })
            i += 1

        if not comics_data:
            flash('Please fill in at least one complete comic entry!', 'error')
            return render_template('add_multiple_comics.html')

        try:
            added_comics = comic_service.add_multiple_comics(comics_data)

            if added_comics:
                flash(f'Successfully added {len(added_comics)} comics!', 'success')
                return redirect(url_for('index'))
            flash('No comics were added. Please check your entries.', 'error')
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('add_multiple_comics.html')

    return render_template('add_multiple_comics.html')


@app.route('/edit/<int:comic_id>', methods=['GET', 'POST'])
def edit_comic(comic_id):
    """Edit an existing comic"""
    comic = comic_service.get_comic_by_id(comic_id)
    if not comic:
        flash('Comic not found!', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        volume = request.form.get('volume', '').strip()
        writer = request.form.get('writer', '').strip()
        artist = request.form.get('artist', '').strip()

        if not all([title, volume, writer, artist]):
            flash('All fields are required!', 'error')
            return render_template('edit_comic.html', comic=comic)

        try:
            updated_comic = comic_service.update_comic(comic_id, title, volume, writer, artist)
            if updated_comic:
                flash(f'Comic "{title}" updated successfully!', 'success')
            else:
                flash('Error updating comic!', 'error')
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('edit_comic.html', comic=comic)

        return redirect(url_for('index'))

    return render_template('edit_comic.html', comic=comic)


@app.route('/delete/<int:comic_id>')
def delete_comic(comic_id):
    """Delete a comic"""
    comic = comic_service.get_comic_by_id(comic_id)
    if comic:
        if comic_service.delete_comic(comic_id):
            flash(f'Comic "{comic.title}" deleted successfully!', 'success')
        else:
            flash('Error deleting comic!', 'error')
    else:
        flash('Comic not found!', 'error')

    return redirect(url_for('index'))


@app.route('/search')
def search():
    """Search comics"""
    query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'title')
    sort_order = request.args.get('order', 'asc')
    page = int(request.args.get('page', 1))
    per_page = 50

    if query:
        comics = comic_service.search_comics(query)

        if sort_by == 'title':
            comics.sort(key=lambda x: x.title.lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'writer':
            comics.sort(key=lambda x: x.writer.lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'artist':
            comics.sort(key=lambda x: x.artist.lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'volume':
            comics.sort(key=lambda x: int(x.volume) if x.volume.isdigit() else 0, reverse=(sort_order == 'desc'))

        total_comics = len(comics)
        total_pages = (total_comics + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_comics = comics[start_idx:end_idx]

        has_prev = page > 1
        has_next = page < total_pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None

        return render_template(
            'index.html',
            comics=paginated_comics,
            search_query=query,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            total_pages=total_pages,
            total_comics=total_comics,
            has_prev=has_prev,
            has_next=has_next,
            prev_page=prev_page,
            next_page=next_page,
            per_page=per_page,
        )

    return redirect(url_for('index'))


@app.route('/api/comics')
def api_get_comics():
    """API endpoint to get all comics"""
    comics = comic_service.get_all_comics()
    return jsonify([
        {
            'id': comic.id,
            'title': comic.title,
            'volume': comic.volume,
            'writer': comic.writer,
            'artist': comic.artist,
        }
        for comic in comics
    ])


@app.route('/api/comics/<int:comic_id>')
def api_get_comic(comic_id):
    """API endpoint to get a specific comic"""
    comic = comic_service.get_comic_by_id(comic_id)
    if comic:
        return jsonify(
            {
                'id': comic.id,
                'title': comic.title,
                'volume': comic.volume,
                'writer': comic.writer,
                'artist': comic.artist,
            }
        )
    return jsonify({'error': 'Comic not found'}), 404


if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')

    app.run(debug=True, host='0.0.0.0', port=5001)
