import sqlite3
import os
import secrets
import datetime
import traceback
from zoneinfo import ZoneInfo

import anthropic
from dotenv import load_dotenv
from flask import Flask, render_template, abort, request, jsonify, redirect
from twilio.rest import Client

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from blog_generator import generate_post

load_dotenv()

app = Flask(__name__)

BLOG_DEFAULT_IMAGE = 'default-dog-care.jpg'
BLOG_DEFAULT_ALT = "Dog care tips from Pookie's Pet Care"

RECAP_IMAGE_MAX_EDGE = 1080
ALLOWED_RECAP_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

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

    conn.execute('''
        CREATE TABLE IF NOT EXISTS recaps (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_name       TEXT NOT NULL,
            service        TEXT,
            visit_notes    TEXT NOT NULL,
            recap_text     TEXT NOT NULL,
            image_filename TEXT,
            share_slug     TEXT UNIQUE NOT NULL,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    conn.close()

# Run once at startup — creates the table if it doesn't exist yet
init_db()

if not HAS_PILLOW:
    print(
        '[RECAP] Pillow not installed — recap photos will save at full size. '
        'Add Pillow to requirements.txt for automatic downscaling.',
        flush=True,
    )

# ── Visit recap helpers ───────────────────────────────────────────────────────

def require_cron_key():
    """Return True when ?key= matches CRON_SECRET."""
    key = request.args.get('key', '')
    return key == os.environ.get('CRON_SECRET', '')


def get_recap_images_dir():
    """Ensure static/recap_images exists and return its path."""
    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'recap_images')
    os.makedirs(images_dir, exist_ok=True)
    return images_dir


def save_recap_image(file_storage):
    """Save an uploaded recap photo. Downscale with Pillow when available."""
    if not file_storage or not file_storage.filename:
        return None

    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_RECAP_EXTENSIONS:
        return None

    token = secrets.token_hex(8)
    images_dir = get_recap_images_dir()

    if HAS_PILLOW:
        try:
            img = Image.open(file_storage.stream)
            img = img.convert('RGB')
            width, height = img.size
            long_edge = max(width, height)
            if long_edge > RECAP_IMAGE_MAX_EDGE:
                ratio = RECAP_IMAGE_MAX_EDGE / long_edge
                img = img.resize(
                    (int(width * ratio), int(height * ratio)),
                    Image.LANCZOS,
                )
            filename = f'recap-{token}.jpg'
            img.save(
                os.path.join(images_dir, filename),
                'JPEG',
                quality=85,
                optimize=True,
            )
            return filename
        except Exception:
            app.logger.exception('Failed to process recap image with Pillow')
            return None

    app.logger.warning(
        'Pillow not installed — saving recap photo without resize. '
        'Add Pillow to requirements.txt for automatic downscaling.'
    )
    save_ext = '.jpg' if ext in ('.jpg', '.jpeg') else ext
    filename = f'recap-{token}{save_ext}'
    file_storage.save(os.path.join(images_dir, filename))
    return filename


def fallback_recap_text(pet_name, service, visit_notes):
    """Simple static recap when the AI call fails."""
    notes = visit_notes.strip()
    first_sentence = notes.split('.')[0].strip() if notes else ''
    if first_sentence and not first_sentence.endswith('.'):
        first_sentence += '.'
    service_bit = f'{service} ' if service else ''
    if first_sentence:
        return f"Had a great {service_bit}visit with {pet_name} today. {first_sentence}"
    return f"Had a great {service_bit}visit with {pet_name} today — all went well!"


def generate_recap_text(pet_name, service, visit_notes):
    """Turn raw visit notes into a warm first-person recap."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        app.logger.warning('ANTHROPIC_API_KEY not set — using fallback recap text')
        return fallback_recap_text(pet_name, service, visit_notes)

    system = (
        "You write short visit recaps for Pookie's Pet Care, a local dog walking and "
        "pet sitting service run by Chris in the South Denver Metro area. "
        "Write 2-3 sentences in first person from Chris's POV. Warm, casual, specific — "
        "like a text to a friend about their pet. No corporate tone, no bullet points, "
        "no greetings or sign-offs. Just the recap."
    )
    user_message = (
        f"Pet name: {pet_name}\n"
        f"Service: {service or 'pet care visit'}\n"
        f"Visit notes: {visit_notes}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=200,
            system=system,
            messages=[{'role': 'user', 'content': user_message}],
        )
        text = response.content[0].text.strip()
        if text:
            return text
    except Exception:
        app.logger.exception('Recap AI generation failed — using fallback')

    return fallback_recap_text(pet_name, service, visit_notes)

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

@app.route('/recap/new')
def recap_new():
    """Mobile-friendly form to create a visit recap card."""
    if not require_cron_key():
        return 'Forbidden', 403
    return render_template('recap_new.html', key=request.args.get('key', ''))


@app.route('/recap/create', methods=['POST'])
def recap_create():
    """Save visit details, generate recap text, and redirect to the shareable card."""
    if not require_cron_key():
        return 'Forbidden', 403

    pet_name = (request.form.get('pet_name') or '').strip()
    service = (request.form.get('service') or '').strip()
    visit_notes = (request.form.get('visit_notes') or '').strip()
    cron_key = request.args.get('key', '')

    if not pet_name or not visit_notes:
        return render_template(
            'recap_new.html',
            key=cron_key,
            error='Pet name and visit notes are required.',
            pet_name=pet_name,
            service=service,
            visit_notes=visit_notes,
        ), 400

    image_filename = save_recap_image(request.files.get('photo'))
    recap_text = generate_recap_text(pet_name, service, visit_notes)
    share_slug = secrets.token_urlsafe(16)

    conn = get_db_connection()
    conn.execute(
        '''
        INSERT INTO recaps (pet_name, service, visit_notes, recap_text, image_filename, share_slug)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (pet_name, service, visit_notes, recap_text, image_filename, share_slug),
    )
    conn.commit()
    conn.close()

    return redirect(f'/recap/{share_slug}')


@app.route('/recap/<share_slug>')
def recap_view(share_slug):
    """Public shareable visit recap card."""
    conn = get_db_connection()
    recap = conn.execute(
        'SELECT * FROM recaps WHERE share_slug = ?', (share_slug,)
    ).fetchone()
    conn.close()
    if recap is None:
        abort(404)
    return render_template('recap_card.html', recap=recap)


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

def booking_received_at_mt():
    """Format current time in Mountain Time for SMS notifications."""
    now = datetime.datetime.now(ZoneInfo('America/Denver'))
    hour = now.hour % 12 or 12
    ampm = 'am' if now.hour < 12 else 'pm'
    return f"{now:%Y-%m-%d} {hour}:{now.minute:02d}{ampm} MT"


def send_booking_notification(submission):
    """SMS Chris when a booking form is submitted. Returns True if sent."""
    print('[SMS DEBUG] send_booking_notification called', flush=True)
    sid = os.environ.get('TWILIO_ACCOUNT_SID')
    token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_phone = os.environ.get('TWILIO_PHONE')
    to_phone = os.environ.get('BOOKING_NOTIFY_PHONE', '+15856233030')

    if not all([sid, token, from_phone, to_phone]):
        print(f'[SMS DEBUG] Skipped — sid={bool(sid)} token={bool(token)} from_phone={from_phone!r} to_phone={to_phone!r}', flush=True)
        return False

    body = (
        "New Pookie's Pet Care booking request:\n"
        f"Received: {booking_received_at_mt()}\n"
        f"Name: {submission['name']}\n"
        f"Phone: {submission['phone']}\n"
        f"Email: {submission['email'] or 'N/A'}\n"
        f"Pet: {submission['pet_name'] or 'N/A'}\n"
        f"Service: {submission['service'] or 'N/A'}\n"
        f"Message: {submission['message'] or 'N/A'}"
    )

    try:
        Client(sid, token).messages.create(
            body=body[:1600],
            from_=from_phone,
            to=to_phone,
        )
        return True
    except Exception:
        print('[SMS DEBUG] Twilio raised an exception:', flush=True)
        traceback.print_exc()
        return False


@app.route('/contact', methods=['POST'])
def contact():
    """Save a booking request from the homepage contact form."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not name or not phone:
        return jsonify({'success': False, 'error': 'Name and phone are required.'}), 400

    email = (data.get('email') or '').strip()
    pet_name = (data.get('pet_name') or '').strip()
    service = (data.get('service') or '').strip()
    message = (data.get('message') or '').strip()

    conn = get_db_connection()
    conn.execute(
        '''
        INSERT INTO contact_submissions (name, phone, email, pet_name, service, message)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (name, phone, email, pet_name, service, message),
    )
    conn.commit()
    conn.close()

    send_booking_notification({
        'name': name,
        'phone': phone,
        'email': email,
        'pet_name': pet_name,
        'service': service,
        'message': message,
    })

    return jsonify({'success': True})

@app.route('/chat', methods=['POST'])
def chat():
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        app.logger.error('ANTHROPIC_API_KEY is not set')
        return jsonify({'error': 'Chat is temporarily unavailable.'}), 503

    data = request.get_json(silent=True) or {}
    messages = data.get('messages', [])

    system = """You are the booking assistant for Pookie's Pet Care LLC, a trusted dog walking and pet sitting service in the South Denver Metro area run by Chris. Be warm, professional, and concise. Keep responses SHORT — 2-3 sentences max. Help visitors understand services and collect contact info so Chris can follow up.

Services: dog walks starting at $30, drop-ins flexible, overnights starting at $75/night.

Collect: pet name/type, service needed, neighborhood/city, dates needed, their name and phone/email.

SERVICE AREA — default to yes, never gatekeep:
Pookie's Pet Care serves the entire South Denver Metro area broadly, including but not limited to: Lone Tree, Parker, Castle Rock, Highlands Ranch, Centennial, Aurora, Bennett, Englewood, Greenwood Village, Littleton, DTC, Cherry Hills Village, Sheridan, Glendale, Columbine, Ken Caryl, Foxfield, and surrounding suburbs. The listed cities are examples, not an exclusive list.

Location rules:
- If a visitor mentions a city or neighborhood in or near the South Denver Metro, treat it as serviceable. Do not tell them you don't serve their area.
- For any other Colorado location you're unsure about, still capture their info and say Chris will follow up to confirm — Chris makes the final call, not you.
- Only flag genuinely out-of-range locations: Fort Collins, Colorado Springs, Boulder, Pueblo, Grand Junction, or anywhere outside Colorado. Even then, stay warm — never just say "we don't serve you" and end the conversation. Say something like: "That's a bit outside Chris's usual area, but go ahead and share your details — he'll reach out and let you know if he can make it work or refer you to someone who can."
- When in doubt, capture the lead. Your job is to collect info, not qualify or disqualify visitors.
- NEVER tell a visitor "we don't serve your area" without offering to take their info anyway. No exceptions.

Once you have all info (name, contact, pet, service, location, dates), confirm and say Chris will reach out within 24 hours. Then output on a new line: LEAD:{"name":"...","pet":"...","service":"...","location":"...","contact":"..."}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system,
            messages=messages,
        )
        return jsonify({"reply": response.content[0].text})
    except Exception:
        app.logger.exception('Chat request failed')
        return jsonify({'error': 'Chat request failed.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)