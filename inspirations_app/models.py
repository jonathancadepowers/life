from django.db import models


class Inspiration(models.Model):
    """
    Stores images and metadata for the inspirations page.
    """
    image = models.ImageField(
        upload_to='inspirations/',
        help_text="Upload an image (book cover, album art, movie poster, etc.)"
    )
    flip_text = models.CharField(
        max_length=200,
        help_text="Text to display when image is flipped (1-2 sentences)"
    )
    type = models.CharField(
        max_length=50,
        help_text="Type of inspiration (e.g., 'Book', 'Film', 'Album', 'TV Show')"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = "Inspiration"
        verbose_name_plural = "Inspirations"

    def __str__(self):
        return f"{self.type}: {self.flip_text[:50]}"
