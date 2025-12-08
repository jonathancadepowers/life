from django.db import models
from cloudinary.models import CloudinaryField


class BookCover(models.Model):
    """
    Singleton model to store the book cover image for the writing page.
    """
    image = CloudinaryField(
        'image',
        help_text="Book cover image displayed on the writing page"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Book Cover'
        verbose_name_plural = 'Book Cover'

    def __str__(self):
        return "Book Cover"

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class WritingPageImage(models.Model):
    """
    Represents an image displayed on the /writing page with its associated excerpt.
    """
    image = CloudinaryField(
        'image',
        help_text="Image file to display on the writing page"
    )
    excerpt = models.TextField(
        help_text="Novel excerpt that appears in the modal when clicking this image"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this image is currently displayed on the page"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Writing Page Image'
        verbose_name_plural = 'Writing Page Images'

    def __str__(self):
        return f"Writing Image {self.id}"


class WritingLog(models.Model):
    """
    Represents a writing log entry tracking days with at least 1.5 hours
    spent writing or thinking about writing.
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the writing log data (e.g., 'Manual', 'Toggl')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from the external source system",
        db_index=True
    )
    log_date = models.DateField(
        help_text="Date of the writing session"
    )
    duration = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        help_text="Duration of writing session in hours",
        null=True,
        blank=True
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-log_date']
        unique_together = ['source', 'source_id']
        indexes = [
            models.Index(fields=['-log_date']),
            models.Index(fields=['source', 'source_id']),
        ]
        verbose_name = 'Writing Log'
        verbose_name_plural = 'Writing Logs'
        db_table = 'writing_logs'

    def __str__(self):
        return f"{self.source} writing log on {self.log_date}"
