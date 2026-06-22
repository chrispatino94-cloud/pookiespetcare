"""
blog_generator.py
-----------------
Standalone script that uses GPT-4o to write a blog post about pet care
and saves it to blog.db (the same database the Flask app reads from).

Run manually:
    python blog_generator.py
    python blog_generator.py --generate-missing-images

Run via Railway: see the Cron Job setup at the bottom of this file.

Requires a .env file in the same directory with:
    OPENAI_API_KEY=sk-...
"""

import os
import json
import random
import sqlite3
import datetime
import argparse
from dotenv import load_dotenv
from openai import OpenAI

from blog_images import (
    DEFAULT_BLOG_IMAGE,
    make_slug,
    generate_and_save_image,
    generate_missing_images,
    get_db_path,
)

load_dotenv()

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

SYSTEM_PROMPT = (
    "You are a friendly, knowledgeable pet care expert writing for Pookie's Pet Care LLC, "
    "a dog walking and pet sitting company in the South Denver Metro area "
    "(Lone Tree, Parker, Castle Rock, Highlands Ranch). "
    "Write in a warm, conversational tone that pet owners will trust and enjoy. "
    "Be practical and specific. Never use generic filler."
)


def generate_post():
    try:
        topic = random.choice(TOPICS)
        print(f"Topic selected: {topic}")

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        user_prompt = f"""Write a blog post about this topic: "{topic}"

Return ONLY a valid JSON object. No markdown, no code fences, no extra text.
Use exactly these three keys:

  "title"   — a catchy, specific title for this post
  "excerpt" — 2–3 sentence summary shown in the blog post listing
  "content" — full 400–600 word post. Use ONLY <p>, <h2>, <ul>, <li> HTML tags.
               Body content only — no <html>, <head>, or <body> wrapper tags."""

        print("Calling GPT-4o...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
        )

        raw_text = response.choices[0].message.content.strip()
        post_data = json.loads(raw_text)

        title = post_data["title"]
        excerpt = post_data["excerpt"]
        content = post_data["content"]
        slug = make_slug(title)

        print(f"Title: {title}")
        print(f"Slug:  {slug}")

        print("Generating topic-matched featured image...")
        image_filename = generate_and_save_image(
            client,
            slug=slug,
            title=title,
            excerpt=excerpt,
            topic=topic,
        )

        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(get_db_path())
        conn.execute(
            """INSERT INTO blog_posts (title, slug, content, excerpt, image_filename, published, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (title, slug, content, excerpt, image_filename, created_at),
        )
        conn.commit()
        conn.close()

        print(f"\n✅  Published: {title}")
        if image_filename == DEFAULT_BLOG_IMAGE:
            print("   (used fallback image — run with --generate-missing-images to retry later)")

    except json.JSONDecodeError as e:
        print(f"❌  GPT returned invalid JSON: {e}")
        print(f"    Raw response was: {raw_text!r}")

    except Exception as e:
        print(f"❌  Error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Generate and publish AI blog posts for Pookie's Pet Care."
    )
    parser.add_argument(
        "--generate-missing-images",
        action="store_true",
        help="Generate unique images for existing posts missing them (no new post)",
    )
    parser.add_argument(
        "--force-images",
        action="store_true",
        help="With --generate-missing-images, overwrite existing slug images",
    )
    args = parser.parse_args()

    if args.generate_missing_images:
        generate_missing_images(force=args.force_images)
    else:
        generate_post()


if __name__ == "__main__":
    main()
