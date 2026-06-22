"""
blog_generator.py
-----------------
Standalone script that uses GPT-4o to write a blog post about pet care
and saves it to blog.db (the same database the Flask app reads from).

Run manually:    python blog_generator.py
Run via Railway: see the Cron Job setup at the bottom of this file.

Requires a .env file in the same directory with:
    OPENAI_API_KEY=sk-...
"""

import os
import json
import random
import sqlite3
import base64
import re
import requests
import datetime
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_BLOG_IMAGE = "default-dog-care.jpg"

# Load .env so OPENAI_API_KEY is available as an environment variable
load_dotenv()

# ── Topic bank ────────────────────────────────────────────────────────────────
# One topic is chosen at random each time this script runs.
# Add more topics here as the blog grows.

TOPICS = [
    "5 signs your dog needs more daily exercise",
    "How to choose a dog walker you can actually trust",
    "Keeping your dog safe and happy during Colorado summers",
    "What to expect from a professional drop-in pet visit",
    "Benefits of consistent daily walks for your dog's mental health",
    "How to prepare your pet for when you travel",
    "Separation anxiety in dogs: signs and simple strategies",
    "Senior dog care: what changes and what doesn't",
    "Puppy socialization tips for South Denver Metro families",
    "Why routine matters more than you think for dogs",
]

# ── Prompts ───────────────────────────────────────────────────────────────────
# The system prompt defines the consistent voice for every post.

SYSTEM_PROMPT = (
    "You are a friendly, knowledgeable pet care expert writing for Pookie's Pet Care LLC, "
    "a dog walking and pet sitting company in the South Denver Metro area "
    "(Lone Tree, Parker, Castle Rock, Highlands Ranch). "
    "Write in a warm, conversational tone that pet owners will trust and enjoy. "
    "Be practical and specific. Never use generic filler."
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_slug(title: str) -> str:
    """
    Convert a post title into a URL-safe slug.
    Example: "How to Pick a Dog Walker!" → "how-to-pick-a-dog-walker"
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)   # strip special characters
    slug = re.sub(r"\s+", "-", slug.strip())     # spaces → hyphens
    slug = re.sub(r"-+", "-", slug)              # collapse double-hyphens
    return slug

# ── Main ──────────────────────────────────────────────────────────────────────

def generate_post():
    try:
        # ── Step 1: Pick a random topic ──────────────────────────────────────
        topic = random.choice(TOPICS)
        print(f"Topic selected: {topic}")

        # ── Step 2: Set up the OpenAI client ─────────────────────────────────
        # OpenAI() automatically reads OPENAI_API_KEY from the environment.
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # ── Step 3: Build the user prompt ────────────────────────────────────
        # We ask GPT to return raw JSON — no markdown, no backticks —
        # so we can parse it directly with json.loads().
        user_prompt = f"""Write a blog post about this topic: "{topic}"

Return ONLY a valid JSON object. No markdown, no code fences, no extra text.
Use exactly these three keys:

  "title"   — a catchy, specific title for this post
  "excerpt" — 2–3 sentence summary shown in the blog post listing
  "content" — full 400–600 word post. Use ONLY <p>, <h2>, <ul>, <li> HTML tags.
               Body content only — no <html>, <head>, or <body> wrapper tags."""

        # ── Step 4: Call GPT-4o ───────────────────────────────────────────────
        print("Calling GPT-4o...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.8,  # a bit of creative variation each week
        )

        # ── Step 5: Parse the JSON response ───────────────────────────────────
        raw_text = response.choices[0].message.content.strip()
        post_data = json.loads(raw_text)  # will raise JSONDecodeError if GPT misbehaves

        title   = post_data["title"]
        excerpt = post_data["excerpt"]
        content = post_data["content"]
        slug    = make_slug(title)

        print(f"Title: {title}")
        print(f"Slug:  {slug}")

        # ── Step 6: Generate a DALL-E 3 image ─────────────────────────────────
        # This runs in its own try/except so a failed image never kills the post.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_filename = None  # stays None if anything below fails

        try:
            print("Generating image with DALL-E 3...")

            # Create static/blog_images/ if it doesn't exist yet
            images_dir = os.path.join(script_dir, "static", "blog_images")
            os.makedirs(images_dir, exist_ok=True)

            # Ask DALL-E 3 for a photo-realistic dog image sized for a blog hero
            image_response = client.images.generate(
                model="gpt-image-1",
                prompt=(
                    f"A warm, friendly photo-realistic image of a happy dog for a blog post "
                    f"titled '{title}'. Bright, clean, professional pet care brand aesthetic. "
                    f"No text in the image."
                ),
                size="1024x1024",      # was 1792x1024 — gpt-image-1 doesn't support that size
                quality="auto",         # was "standard" — gpt-image-1 uses low/medium/high/auto
                n=1,
            )

            # The response contains a temporary URL; download and save locally
            image_data = base64.b64decode(image_response.data[0].b64_json)

            image_filename = f"{slug}.jpg"
            img_path = os.path.join(images_dir, image_filename)
            with open(img_path, "wb") as f:
                f.write(image_data)

            print(f"Image saved: static/blog_images/{image_filename}")

        except Exception as img_err:
            # Image generation failed — use the shared fallback so cards never look broken
            print(f"⚠️  Image generation failed, using fallback: {img_err}")
            image_filename = DEFAULT_BLOG_IMAGE

        # ── Step 7: Save to blog.db ────────────────────────────────────────────
        # os.path.abspath(__file__) ensures we find blog.db relative to THIS script,
        # not whatever directory the cron job runs from.
        db_path = os.path.join(script_dir, "blog.db")
        conn = sqlite3.connect(db_path)

        # published=1 means the post goes live immediately on the site.
        # created_at is set explicitly so each post gets the real publish date.
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            """INSERT INTO blog_posts (title, slug, content, excerpt, image_filename, published, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (title, slug, content, excerpt, image_filename, created_at),
        )
        conn.commit()
        conn.close()

        print(f"\n✅  Published: {title}")

    except json.JSONDecodeError as e:
        # GPT occasionally returns markdown-wrapped JSON despite instructions.
        # If that happens, check raw_text below and adjust the prompt.
        print(f"❌  GPT returned invalid JSON: {e}")
        print(f"    Raw response was: {raw_text!r}")

    except Exception as e:
        print(f"❌  Error: {e}")
        raise  # re-raise so Railway marks the cron job as failed

if __name__ == "__main__":
    generate_post()
