from collections import defaultdict
from typing import Any

from promise import Promise

from ....core.db.connection import allow_writer_in_context
from ....webhook.event_types import WebhookEventSyncType
from ...app.dataloaders.apps import AppsByEventTypeLoader
from ...checkout.dataloaders.checkout_infos import (
    CheckoutInfoByCheckoutTokenLoader,
    CheckoutLinesInfoByCheckoutTokenLoader,
)
from ...core.dataloaders import DataLoader
from .models import WebhooksByEventTypeLoader
from .request_context import (
    PayloadsRequestContextByEventTypeLoader,
)


class PregeneratedCheckoutTaxPayloadsByCheckoutTokenLoader(DataLoader):
    context_key = "pregenerated_checkout_tax_payloads_by_checkout_token"

    def batch_load(self, keys):
        """Fetch pregenerated tax payloads for checkouts.

        This loader is used to fetch pregenerated tax payloads for checkouts.

        return: A dict of tax payloads for checkouts.

        Example:
        {
            "checkout_token": {
                "app_id": {
                    "query_hash": {
                        <payload>
                    }
                }
            }
        }

        """
        results: dict[str, dict[int, dict[str, dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(dict)
        )

        event_type = WebhookEventSyncType.CHECKOUT_CALCULATE_TAXES

        @allow_writer_in_context(self.context)
        def generate_payloads(data):
            checkouts_info, checkout_lines_info, apps, request_context, webhooks = data
            promises = []
            for checkout_info, lines_info in zip(checkouts_info, checkout_lines_info):
                pass


            def return_payloads(_payloads):
                return [results[str(checkout_token)] for checkout_token in keys]

            return Promise.all(promises).then(return_payloads)

        checkouts_info = CheckoutInfoByCheckoutTokenLoader(self.context).load_many(keys)
        lines = CheckoutLinesInfoByCheckoutTokenLoader(self.context).load_many(keys)
        apps = AppsByEventTypeLoader(self.context).load(event_type)
        request_context = PayloadsRequestContextByEventTypeLoader(self.context).load(
            event_type
        )
        webhooks = WebhooksByEventTypeLoader(self.context).load(event_type)
        return Promise.all(
            [checkouts_info, lines, apps, request_context, webhooks]
        ).then(generate_payloads)
