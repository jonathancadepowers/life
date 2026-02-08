#!/usr/bin/env python3
"""
Script to upload inspirations directly to production database and Cloudinary.
Run this locally with your images directory.
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django settings for production
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lifetracker.settings")
os.environ["DATABASE_URL"] = os.getenv("HEROKU_DATABASE_URL", "")  # You'll need to set this

django.setup()

from django.core.management import call_command  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload_to_production.py /path/to/images")
        sys.exit(1)

    directory = sys.argv[1]
    call_command("import_inspirations", directory)
