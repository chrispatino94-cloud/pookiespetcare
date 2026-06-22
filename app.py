import sqlite3
import os
import datetime
from flask import Flask, render_template, abort, request

from blog_generator import generate_post

app = Flask(__name__)

BLOG_DEFAULT_IMAGE = 'default-dog-care.jpg'
BLOG_DEFAULT_ALT = "Dog care tips from Pookie's Pet Care"

def get_blog_image_filename(image_filename):
    """Return the post image or the shared fallback asset."""
    if image_filename:
        return image_filename
    return BLOG_DEFAULT_IMAGE

@app.context_processor
def blog_context():
    return {
        'blog_image': get_blog_image_filename,
        'blog_default_alt': BLOG_DEFAULT_ALT,
    }

# ── Database helpers ──────────────────────────────────────────────────────────

def get_db_connection():
    """Open a connection to blog.db and enable dict-like column access."""
    conn = sqlite3.connect('blog.db')
    conn.row_factory = sqlite3.Row  # lets us do post['title'] instead of post[0]
    return conn

def init_db():
    """Create the blog_posts table on first run — safe to call every startup."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blog_posts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            title          TEXT NOT NULL,
            slug           TEXT UNIQUE NOT NULL,
            content        TEXT NOT NULL,
            excerpt        TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published      INTEGER DEFAULT 1
        )
    ''')
    conn.commit()

    # Add image_filename to existing tables that were created before this column existed.
    # ALTER TABLE fails silently if the column is already there — that's intentional.
    try:
        conn.execute('ALTER TABLE blog_posts ADD COLUMN image_filename TEXT')
        conn.commit()
    except Exception:
        pass  # column already exists, nothing to do

    conn.close()

# Run once at startup — creates the table if it doesn't exist yet
init_db()

# ── Template filter ───────────────────────────────────────────────────────────

@app.template_filter('format_date')
def format_date(value):
    """Convert '2026-06-16 10:30:00' into 'June 16, 2026' for templates."""
    if value is None:
        return ''
    if isinstance(value, str):
        value = value[:10]  # slice off just the YYYY-MM-DD portion
        dt = datetime.datetime.strptime(value, '%Y-%m-%d')
    else:
        dt = value
    return dt.strftime('%B %-d, %Y')  # %-d removes the leading zero (Linux/Mac only)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/blog')
def blog():
    """Show all published posts, newest first."""
    conn = get_db_connection()
    posts = conn.execute(
        'SELECT * FROM blog_posts WHERE published = 1 ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('blog.html', posts=posts)

@app.route('/blog/<int:post_id>')
def blog_post(post_id):
    """Show a single post by its database id. Returns 404 if not found."""
    conn = get_db_connection()
    post = conn.execute(
        'SELECT * FROM blog_posts WHERE id = ?', (post_id,)
    ).fetchone()
    conn.close()
    if post is None:
        abort(404)
    return render_template('blog_post.html', post=post)

@app.route('/run-blog-generator')
def run_blog_generator():
    key = request.args.get('key', '')
    if key != os.environ.get('CRON_SECRET', ''):
        return "Forbidden", 403
    try:
        generate_post()
        return "Blog post generated successfully", 200
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
