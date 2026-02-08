#!/usr/bin/env python3
"""
Bulk upload inspirations to production database and Cloudinary.
"""
import os
import psycopg2
from PIL import Image
import io
import cloudinary
import cloudinary.uploader
from django.utils.text import slugify

# Cloudinary configuration
cloudinary.config(cloud_name="dswnu77yo", api_key="435935979376128", api_secret="WQETj-mA6F8qJblK4G6Gnus2G4U")

# Database configuration
DATABASE_URL = (
    "postgres://ufsql79d63cfr8:p6bbc2ad7b1a6717eece4f26395614025a47e42118448cd95f2a2a4f268c5506a"
    "@cd7f19r8oktbkp.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dc1cfgkvek5j91"
)


def parse_filename(filename):
    """Parse filename to extract type and title."""
    name_without_ext = os.path.splitext(filename)[0]
    parts = name_without_ext.split("_", 1)

    if len(parts) != 2:
        return None, None

    type_raw, title_raw = parts

    # Convert type to proper case
    type_raw_lower = type_raw.lower()
    if type_raw_lower in ["tvshow", "tv_show", "tv show"]:
        type_value = "TV Show"
    elif type_raw_lower in ["podcastseries", "podcast_series", "podcast series"]:
        type_value = "Podcast Series"
    else:
        type_value = type_raw.capitalize()

    # Convert title to proper case
    title = " ".join(word.capitalize() for word in title_raw.replace("_", " ").split())

    return type_value, title


def resize_image(image_path):
    """Resize image to 256x362 and return bytes."""
    img = Image.open(image_path)
    img = img.resize((256, 362), Image.Resampling.LANCZOS)

    # Convert to RGB if necessary
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Save to BytesIO
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    output.seek(0)

    return output


def upload_to_cloudinary(image_bytes, title):
    """Upload image to Cloudinary."""
    slugified_title = slugify(title)
    filename = f"inspirations/{slugified_title}"

    result = cloudinary.uploader.upload(image_bytes, public_id=filename, overwrite=True, resource_type="image")

    return result["secure_url"]


def main():
    directory = "/Users/jonathanpowers/Desktop/jonathanpowers.notion.site/pics"

    # Get all image files
    image_files = [f for f in os.listdir(directory) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]

    print(f"Found {len(image_files)} images to import")

    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    imported_count = 0
    skipped_count = 0
    error_count = 0

    for filename in image_files:
        try:
            type_value, title = parse_filename(filename)

            if not type_value or not title:
                print(f"⚠️  Skipping {filename}: Invalid filename format")
                skipped_count += 1
                continue

            # Check if already exists
            cur.execute(
                "SELECT id FROM inspirations_app_inspiration WHERE title = %s AND type = %s", (title, type_value)
            )
            if cur.fetchone():
                print(f"⚠️  Skipping {filename}: {title} ({type_value}) already exists")
                skipped_count += 1
                continue

            # Resize image
            image_path = os.path.join(directory, filename)
            image_bytes = resize_image(image_path)

            # Upload to Cloudinary
            print(f"📤 Uploading {title} ({type_value}) to Cloudinary...")
            cloudinary_url = upload_to_cloudinary(image_bytes, title)

            # Insert into database
            cur.execute(
                """
                INSERT INTO inspirations_app_inspiration
                (image, title, flip_text, type, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                (cloudinary_url, title, "", type_value),
            )
            conn.commit()

            print(f"✅ Imported: {title} ({type_value})")
            imported_count += 1

        except Exception as e:
            print(f"❌ Error processing {filename}: {str(e)}")
            error_count += 1
            conn.rollback()

    cur.close()
    conn.close()

    # Summary
    print("\n" + "=" * 50)
    print("Import complete!")
    print(f"  ✅ Imported: {imported_count}")
    print(f"  ⚠️  Skipped: {skipped_count}")
    print(f"  ❌ Errors: {error_count}")
    print("=" * 50)


if __name__ == "__main__":
    main()
