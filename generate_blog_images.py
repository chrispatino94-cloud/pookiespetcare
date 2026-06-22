#!/usr/bin/env python3
"""
generate_blog_images.py
-----------------------
Generate unique featured images for blog posts that are missing them
or still using the shared fallback.

Usage:
    python generate_blog_images.py
    python generate_blog_images.py --force
"""

import argparse
from dotenv import load_dotenv

from blog_images import generate_missing_images

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Generate unique featured images for blog posts."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate images even when a slug-based file already exists",
    )
    args = parser.parse_args()
    generate_missing_images(force=args.force)


if __name__ == "__main__":
    main()
