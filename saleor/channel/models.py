from django.db import models

from ..core.models import ModelWithMetadata
from ..permission.enums import ChannelPermissions


class Channel(ModelWithMetadata):
    name = models.CharField(max_length=250)
    is_active = models.BooleanField(default=False)
    slug = models.SlugField(max_length=255, unique=True)


    class Meta(ModelWithMetadata.Meta):
        ordering = ("slug",)
        app_label = "channel"
        permissions = (
            (
                ChannelPermissions.MANAGE_CHANNELS.codename,
                "Manage channels.",
            ),
        )

    def __str__(self):
        return self.slug
