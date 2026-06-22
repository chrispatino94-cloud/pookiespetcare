"""
blog_images.py
--------------
Shared helpers for generating unique, topic-matched blog featured images.
Used by blog_generator.py and generate_blog_images.py.
"""

import os
import re
import base64
import sqlite3
from typing import Optional

from openai import OpenAI

DEFAULT_BLOG_IMAGE = "default-dog-care.jpg"

BRAND_STYLE = (
    "Realistic professional pet-care photography for a trusted local dog walking "
    "and pet sitting business. Natural human-and-dog interaction, warm soft light, "
    "real neighborhood or home setting, South Denver Colorado feel, trustworthy "
    "caregiver energy, clean composition, no text, no logos, no watermark, "
    "not cartoon, not overly staged, not glossy stock photo."
)

# Varied dog descriptions — slug picks one so posts don't all look the same breed.
DOG_VARIATIONS = [
    "a medium-sized brindle mixed-breed dog",
    "a small wiry tan-and-white terrier mix",
    "a black-and-white border collie",
    "a stocky brown-and-white pit bull mix",
    "a fluffy cream spitz-type dog",
    "a lean gray weimaraner",
    "a short-coated chocolate labrador",
    "a scruffy australian shepherd mix with merle markings",
    "a compact black corgi mix",
    "a medium red heeler mix with upright ears",
    "a long-coated tricolor beagle mix",
    "a muscular blue-gray staffordshire mix",
]


def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def get_images_dir():
    images_dir = os.path.join(get_script_dir(), "static", "blog_images")
    os.makedirs(images_dir, exist_ok=True)
    return images_dir


def get_db_path():
    return os.path.join(get_script_dir(), "blog.db")


def make_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def dog_description(slug: str) -> str:
    """Return a consistent but varied dog description for a given post slug."""
    idx = sum(ord(c) for c in slug) % len(DOG_VARIATIONS)
    return DOG_VARIATIONS[idx]


def infer_scene(
    title: str,
    excerpt: str,
    slug: str,
    topic: Optional[str] = None,
) -> str:
    """Build a topic-specific, human-centered scene from post metadata."""
    text = f"{title} {excerpt} {topic or ''}".lower()
    dog = dog_description(slug)

    if any(w in text for w in ("dog walker", "choose a walker", "trustworthy walker", "walking service")):
        return (
            f"{dog.capitalize()} walking beside a caring local dog walker on a sunny "
            "neighborhood sidewalk or park path in South Denver, leash visible, walker "
            "shown naturally from behind or waist-down with no visible face, warm Colorado light"
        )
    if any(w in text for w in ("summer", "colorado summer", "heat", "hot weather", "thrives in colorado")):
        return (
            f"{dog.capitalize()} relaxing in shade while a caregiver kneels nearby placing "
            "or refilling a water bowl, sunny Colorado park or shaded backyard, safe summer "
            "pet care feeling, caregiver shown from waist-down or hands only"
        )
    if any(w in text for w in ("travel", "journey", "trip", "away", "vacation", "leaving your pet")):
        return (
            f"{dog.capitalize()} resting calmly at home on a couch or rug while a pet sitter "
            "gently checks on them, travel bag and keys subtly on a side table, cozy real "
            "home interior, reassuring care while owner is away, caregiver partially visible"
        )
    if any(w in text for w in ("drop-in", "drop in", "visit", "check-in")):
        return (
            f"{dog.capitalize()} happily greeting a caregiver at a residential front door, "
            "leash or treat pouch visible on caregiver's hip, friendly local drop-in visit "
            "moment, caregiver shown from behind or waist-down"
        )
    if any(w in text for w in ("overnight", "house sitting", "house-sitting", "evening")):
        return (
            f"{dog.capitalize()} resting indoors near a blanket or dog bed while a caregiver "
            "sits nearby in a calm real home living room, warm evening window light, safe "
            "overnight care, caregiver partially visible without face shown"
        )
    if any(w in text for w in ("winter", "snow", "cold", "ice")):
        return (
            f"{dog.capitalize()} walking safely with a caregiver on a lightly snowy Colorado "
            "sidewalk, leash visible, caregiver in warm jacket shown from behind, safe winter "
            "pet care, soft overcast daylight"
        )
    if any(w in text for w in ("puppy", "socialization", "socialize")):
        return (
            f"A young {dog.replace('a ', '')} meeting a kneeling caregiver in a quiet South "
            "Denver park, gentle positive socialization moment, caregiver's hands offering "
            "a treat, soft natural light"
        )
    if any(w in text for w in ("senior", "older dog", "aging")):
        return (
            f"An older {dog.replace('a ', '')} on a slow peaceful neighborhood walk beside "
            "a patient caregiver, leash held gently, quiet tree-lined sidewalk, compassionate "
            "senior pet care, caregiver from behind"
        )
    if any(w in text for w in ("anxiety", "separation", "stress")):
        return (
            f"{dog.capitalize()} relaxing on a cozy home rug while a caregiver sits nearby "
            "offering calm presence, comforting toys within reach, peaceful reassuring pet "
            "care atmosphere, warm interior light"
        )
    if any(w in text for w in ("exercise", "active", "energy", "walk")):
        return (
            f"{dog.capitalize()} on a leash beside a caregiver during an active neighborhood "
            "walk on a real suburban sidewalk, healthy movement, bright natural light, "
            "caregiver shown from waist-down"
        )

    return (
        f"{dog.capitalize()} receiving gentle care from a local pet caregiver in a real home "
        f"or neighborhood setting related to: {title}. {excerpt[:140].strip()}"
    )


def build_image_prompt(
    title: str,
    excerpt: str,
    slug: str,
    topic: Optional[str] = None,
) -> str:
    """Combine a topic-specific scene with the Pookie's brand style."""
    scene = infer_scene(title, excerpt, slug, topic)
    variety_note = (
        "Avoid golden retriever or generic lab look. "
        "Make this feel like a candid real moment, not a stock photo."
    )
    return f"{scene}. {variety_note} {BRAND_STYLE}"


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environment")
    return OpenAI(api_key=api_key)


def image_path_for_slug(slug: str) -> str:
    return os.path.join(get_images_dir(), f"{slug}.jpg")


def slug_image_exists(slug: str) -> bool:
    return os.path.isfile(image_path_for_slug(slug))


def needs_image_generation(image_filename: Optional[str], slug: str) -> bool:
    """True when a post should get a newly generated image."""
    if not image_filename or image_filename == DEFAULT_BLOG_IMAGE:
        return True
    expected = f"{slug}.jpg"
    if image_filename != expected:
        return True
    return not os.path.isfile(image_path_for_slug(slug))


def generate_and_save_image(
    client: OpenAI,
    slug: str,
    title: str,
    excerpt: str,
    topic: Optional[str] = None,
    force: bool = False,
) -> str:
    """
    Generate a unique featured image for a post.
    Returns the saved filename, or DEFAULT_BLOG_IMAGE on failure.
    Does not overwrite an existing slug image unless force=True.
    """
    image_filename = f"{slug}.jpg"
    img_path = image_path_for_slug(slug)

    if not force and os.path.isfile(img_path):
        print(f"  Image already exists, skipping: static/blog_images/{image_filename}")
        return image_filename

    prompt = build_image_prompt(title, excerpt, slug, topic)
    print(f"  Image prompt: {prompt[:140]}...")

    try:
        print("  Generating image with gpt-image-1...")
        image_response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            quality="auto",
            n=1,
        )
        image_data = base64.b64decode(image_response.data[0].b64_json)
        with open(img_path, "wb") as f:
            f.write(image_data)
        print(f"  Image saved: static/blog_images/{image_filename}")
        return image_filename
    except Exception as err:
        print(f"  ⚠️  Image generation failed, using fallback: {err}")
        return DEFAULT_BLOG_IMAGE


def update_post_image(post_id: int, image_filename: str) -> None:
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        "UPDATE blog_posts SET image_filename = ? WHERE id = ?",
        (image_filename, post_id),
    )
    conn.commit()
    conn.close()


def generate_missing_images(force: bool = False) -> None:
    """
    Backfill or regenerate blog images.
    With force=True, regenerates all posts even if slug images already exist.
    """
    client = get_openai_client()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    posts = conn.execute(
        "SELECT id, title, slug, excerpt, image_filename FROM blog_posts ORDER BY id"
    ).fetchall()
    conn.close()

    if not posts:
        print("No blog posts found.")
        return

    mode = "force-regenerating all" if force else "checking for missing or fallback"
    print(f"{mode} — {len(posts)} post(s)\n")

    for post in posts:
        post_id = post["id"]
        title = post["title"]
        slug = post["slug"]
        excerpt = post["excerpt"] or ""
        current_image = post["image_filename"]

        if not force and not needs_image_generation(current_image, slug):
            print(f"[{post_id}] {title}")
            print(f"  Already has unique image: {current_image}\n")
            continue

        print(f"[{post_id}] {title}")
        image_filename = generate_and_save_image(
            client,
            slug=slug,
            title=title,
            excerpt=excerpt,
            force=force,
        )

        if image_filename != current_image or force:
            update_post_image(post_id, image_filename)
            print(f"  Database updated: image_filename = {image_filename}\n")
        else:
            print(f"  No database change needed.\n")

    print("Done.")
