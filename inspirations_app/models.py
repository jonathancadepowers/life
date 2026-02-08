from django.db import models
from django.utils.text import slugify
import os


def inspiration_image_path(instance, filename):
    """Generate upload path using title if available, otherwise use original filename."""
    # Get file extension
    ext = os.path.splitext(filename)[1]

    # Use title if available, otherwise use original filename
    if instance.title:
        # Slugify the title and append extension
        new_filename = f"{slugify(instance.title)}{ext}"
    else:
        new_filename = filename

    return f"inspirations/{new_filename}"


class Inspiration(models.Model):
    """
    Stores images and metadata for the inspirations page.
    """

    TYPE_CHOICES = [
        ("Film", "Film"),
        ("Book", "Book"),
        ("Album", "Album"),
        ("TV Show", "TV Show"),
        ("Podcast Series", "Podcast Series"),
        ("Article", "Article"),
        ("Other", "Other"),
    ]

    image = models.ImageField(
        upload_to=inspiration_image_path, help_text="Upload an image (book cover, album art, movie poster, etc.)"
    )
    title = models.CharField(
        max_length=200, blank=True, help_text="Title of the work (e.g., book title, film name, album name)"
    )
    flip_text = models.CharField(
        max_length=200, blank=True, help_text="Text to display when image is flipped (1-2 sentences)"
    )
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, help_text="Type of inspiration")
    url = models.URLField(
        max_length=200, blank=True, default="", help_text="URL link (e.g., trailer, Goodreads, Spotify, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Inspiration"
        verbose_name_plural = "Inspirations"

    def __str__(self):
        return f"{self.type}: {self.flip_text[:50]}"
