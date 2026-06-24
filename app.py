import sqlite3
import os
import datetime
from flask import Flask, render_template, abort, request, jsonify

from blog_generator import generate_post

app = Flask(__name__)

BLOG_DEFAULT_IMAGE = 'default-dog-care.jpg'
BLOG_DEFAULT_ALT = "Dog care tips from Pookie's Pet Care"

# Google Business Profile links.
# For "Leave a review": Google Business Profile → Ask for reviews → copy link,
# or use: https://search.google.com/local/writereview?placeid=YOUR_PLACE_ID
GOOGLE_REVIEWS_URL = (
    "https://www.google.com/search?sca_esv=6afbdd065017325d&hl=en-US"
    "&rlz=1CDGOYI_enUS972US972&cs=1&output=search&kgmid=%2Fg%2F11m68zbvk2"
    "&q=Pookie%E2%80%99s%20Pet%20Care%20-%20Centennial%20Dog%20Walking%20and%20Pet%20Sitting"
    "&shem=epsd1%2Cltac%2Crimspwouoe&shndl=30&source=sh%2Fx%2Floc%2Fact%2Fm4%2F3"
)
GOOGLE_WRITE_REVIEW_URL = None


def get_google_write_review_url():
    """Return write-review URL only when explicitly set."""
    return GOOGLE_WRITE_REVIEW_URL

GOOGLE_RATING = {
    "score": "5.0",
    "count": 9,
    "stars": 5,
}

# Homepage visit gallery — real pet photos in static/gallery/
# Chris + husky selfie is on the About card only; gallery uses pet visit photos.
VISIT_PHOTOS = [
    {
        "file": "gallery/white-dog-yard-play.jpeg",
        "alt": "White dog playing in the yard during a visit",
    },
    {
        "file": "gallery/happy-walk-small-dog.jpeg",
        "alt": "Small dog on a happy neighborhood walk",
    },
    {
        "file": "gallery/pugs-car-ride.jpeg",
        "alt": "Two pugs ready for a car ride after pet care",
    },
    {
        "file": "gallery/gentle-dog-cuddle.jpeg",
        "alt": "Gentle cuddle with a happy dog at home",
    },
    {
        "file": "gallery/black-terrier-yard-play.jpeg",
        "alt": "Black terrier playing in the yard during a visit",
    },
    {
        "file": "gallery/chris-husky-selfie.jpeg",
        "alt": "Chris with a husky during a pet care visit",
    },
]

# Real Google reviews for Pookie's Pet Care.
# Only use client pet photos with permission — set optional "photo" to a static path when approved.
TESTIMONIALS = [
    {
        "rating": 5,
        "quote": (
            "We've been using Chris for walks and drop ins for almost 2 years. "
            "He's phenomenal! We have 3 very high energy pups and..."
        ),
        "name": "Kymberlee Chamberlain",
        "location": "Colorado",
        "service": "Walks & drop-ins",
        # "photo": "review_photos/kymberlee-pups.jpg",  # TODO: add with client permission
    },
    {
        "rating": 5,
        "quote": (
            "We have a 4 yr old Bernedoodle that is a crazy puppy and Chris handles him so well, "
            "we have been working with Chris for..."
        ),
        "name": "Anthony Fopp",
        "location": "Colorado",
        "service": "Bernedoodle care",
    },
    {
        "rating": 5,
        "quote": (
            "Our dog Morphi absolutely loves Chris! Even though our dog isn't the most "
            "well-behaved during walks, somehow Chris gets..."
        ),
        "name": "Brianda Cortez",
        "location": "Colorado",
        "service": "Dog walking",
    },
    {
        "rating": 5,
        "quote": (
            "Chris does a great job watching our cat, Sage! He's responsive, available on short "
            "notice, and goes above and beyond..."
        ),
        "name": "Kaylynn Crawford",
        "location": "Colorado",
        "service": "Cat care",
    },
    {
        "rating": 5,
        "quote": (
            "We had an amazing experience with Chris taking care of our 2 pitties and our kitty. "
            "He stayed overnight, kenneling when..."
        ),
        "name": "Dee Dee Curry",
        "location": "Colorado",
        "service": "Overnight pet care",
    },
    {
        "rating": 5,
        "quote": (
            "Excellent dog sitter. Chris is great. He's organized, reliable, great with dogs, "
            "and communicates effectively. He did an excellent job managing our 3 dogs for a week. "
            "Greatly appreciated Chris. Will be back."
        ),
        "name": "Anthony Nardecchia",
        "location": "Colorado",
        "service": "Week-long dog sitting",
    },
    {
        "rating": 5,
        "quote": (
            "Chris did an amazing job taking care of my two goldendoodles. He's always available "
            "when we are taking a last-minute..."
        ),
        "name": "Sarah Simon",
        "location": "Colorado",
        "service": "Goldendoodle care",
    },
    {
        "rating": 5,
        "quote": (
            "Chris' prices are reasonable, he is very communicative, and is always on time. "
            "Even when I tasked him with walking my..."
        ),
        "name": "Dominique Bayona",
        "location": "Colorado",
        "service": "Dog care",
    },
    {
        "rating": 5,
        "quote": (
            "Chris did a wonderful job dropping in and letting my dog outside. He provided daily "
            "updates and went above and beyond in..."
        ),
        "name": "Bruce Masters",
        "location": "Colorado",
        "service": "Drop-in visits",
    },
]

# Number of review cards shown on the homepage (full list kept for future use).
HOMEPAGE_REVIEW_COUNT = 6

def get_blog_image_filename(image_filename):
    """Return the post image if the file exists, otherwise the shared fallback."""
    if image_filename:
        img_path = os.path.join('static', 'blog_images', image_filename)
        if os.path.isfile(img_path):
            return image_filename
    fallback_path = os.path.join('static', 'blog_images', BLOG_DEFAULT_IMAGE)
    if os.path.isfile(fallback_path):
        return BLOG_DEFAULT_IMAGE
    return image_filename or BLOG_DEFAULT_IMAGE

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

    conn.execute('''
        CREATE TABLE IF NOT EXISTS contact_submissions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            phone      TEXT NOT NULL,
            email      TEXT,
            pet_name   TEXT,
            service    TEXT,
            message    TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

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
    return render_template(
        'index.html',
        testimonials=TESTIMONIALS[:HOMEPAGE_REVIEW_COUNT],
        google_reviews_url=GOOGLE_REVIEWS_URL,
        google_write_review_url=get_google_write_review_url(),
        google_rating=GOOGLE_RATING,
        visit_photos=VISIT_PHOTOS,
    )

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

@app.route('/contact', methods=['POST'])
def contact():
    """Save a booking request from the homepage contact form."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not name or not phone:
        return jsonify({'success': False, 'error': 'Name and phone are required.'}), 400

    conn = get_db_connection()
    conn.execute(
        '''
        INSERT INTO contact_submissions (name, phone, email, pet_name, service, message)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            name,
            phone,
            (data.get('email') or '').strip(),
            (data.get('pet_name') or '').strip(),
            (data.get('service') or '').strip(),
            (data.get('message') or '').strip(),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/chat', methods=['POST'])
def chat():
    import anthropic
    data = request.json
    messages = data.get('messages', [])
    
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    system = """You are the booking assistant for Pookie's Pet Care LLC, a trusted dog walking and pet sitting service in the South Denver Metro area run by Chris. Be warm, professional, and concise. Keep responses SHORT — 2-3 sentences max. Help visitors understand services and collect contact info so Chris can follow up. Collect: pet name/type, service needed, neighborhood, their name and phone/email. Services: dog walks starting at $30, drop-ins flexible, overnights starting at $75/night. Area: Lone Tree, Parker, Castle Rock, Highlands Ranch, Centennial, Aurora, Bennett. Once you have all info, confirm and say Chris will reach out within 24 hours. Then output on a new line: LEAD:{"name":"...","pet":"...","service":"...","location":"...","contact":"..."}"""
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system,
        messages=messages
    )
    return jsonify({"reply": response.content[0].text})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)