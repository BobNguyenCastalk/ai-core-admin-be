import json
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site

from ...core.utils import build_absolute_uri
from ...core.utils.json_serializer import HTMLSafeJSON

if TYPE_CHECKING:
    from ...order.models import Order, OrderLine


def get_organization():
    site = Site.objects.get_current()
    return {"@type": "Organization", "name": site.name}