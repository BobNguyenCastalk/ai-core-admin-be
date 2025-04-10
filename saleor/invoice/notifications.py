from typing import TYPE_CHECKING, Optional

from ..core.notification.utils import get_site_context
from ..core.notify import NotifyEventType, NotifyHandler
from ..graphql.core.utils import to_global_id_or_none

if TYPE_CHECKING:
    from ..account.models import User
    from ..app.models import App
    from ..plugins.manager import PluginsManager
    from .models import Invoice


def get_invoice_payload(invoice):
    return {
        "id": to_global_id_or_none(invoice),
        "number": invoice.number,
        "download_url": invoice.url,
        "order_id": to_global_id_or_none(invoice.order),
    }