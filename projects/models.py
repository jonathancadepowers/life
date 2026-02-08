from django.db import models


class Project(models.Model):
    """
    Represents a project that can be associated with time logs.
    Maps to Toggl Projects.
    """

    project_id = models.IntegerField(primary_key=True, help_text="Unique project identifier (Toggl Project ID)")
    display_string = models.CharField(max_length=255, help_text="Human-readable project name")

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_string"]
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self):
        return self.display_string
