from django.core.exceptions import ValidationError
from django.db import models

from ..account.models import User
from ..app.models import App, AppInstallation
from . import THUMBNAIL_SIZES, ThumbnailFormat


def validate_thumbnail_size(size: int):
    if size not in THUMBNAIL_SIZES:
        available_sizes = [str(size) for size in THUMBNAIL_SIZES]
        raise ValidationError(
            f"Only following sizes are available: {', '.join(available_sizes)}."
        )


class Thumbnail(models.Model):
    image = models.ImageField(upload_to="thumbnails")
    size = models.PositiveIntegerField(validators=[validate_thumbnail_size])
    format = models.CharField(
        max_length=32, null=True, blank=True, choices=ThumbnailFormat.CHOICES
    )
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="thumbnails"
    )
    app = models.ForeignKey(
        App, null=True, blank=True, on_delete=models.CASCADE, related_name="thumbnails"
    )
    app_installation = models.ForeignKey(
        AppInstallation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="thumbnails",
    )
