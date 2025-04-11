import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, cast

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from prices import Money, TaxedMoney

from ..checkout import base_calculations
from ..core.db.connection import allow_writer
from ..core.prices import quantize_price
from ..core.taxes import (
    TaxData,
    TaxDataError,
    TaxDataErrorMessage,
    zero_money,
    zero_taxed_money,
)
from ..payment.models import TransactionItem
from ..plugins import PLUGIN_IDENTIFIER_PREFIX
from .fetch import ShippingMethodInfo, find_checkout_line_info
from .models import Checkout
from .payment_utils import update_checkout_payment_statuses

if TYPE_CHECKING:
    from ..account.models import Address
    from ..plugins.manager import PluginsManager
    from .fetch import CheckoutInfo, CheckoutLineInfo

logger = logging.getLogger(__name__)


def checkout_shipping_price(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
) -> "TaxedMoney":
    """Return checkout shipping price.

    It takes in account all plugins.
    """
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    currency = checkout_info.checkout.currency
    checkout_info, _ = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
    )
    return quantize_price(checkout_info.checkout.shipping_price, currency)


def checkout_shipping_tax_rate(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> Decimal:
    """Return checkout shipping tax rate.

    It takes in account all plugins.
    """
    checkout_info, _ = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
    )
    return checkout_info.checkout.shipping_tax_rate


def checkout_subtotal(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
) -> "TaxedMoney":
    """Return the total cost of all the checkout lines, taxes included.

    It takes in account all plugins.
    """
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    currency = checkout_info.checkout.currency
    checkout_info, _ = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
    )
    return quantize_price(checkout_info.checkout.subtotal, currency)


def calculate_checkout_total_with_gift_cards(
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
    force_update: bool = False,
) -> "TaxedMoney":
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    total = checkout_total(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
        force_update=force_update,
    )

    return max(total, zero_taxed_money(total.currency))


def checkout_total(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
    force_update: bool = False,
) -> "TaxedMoney":
    """Return the total cost of the checkout.

    Total is a cost of all lines and shipping fees, minus checkout discounts,
    taxes included.

    It takes in account all plugins.
    """
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    currency = checkout_info.checkout.currency
    checkout_info, _ = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
        force_update=force_update,
    )
    return quantize_price(checkout_info.checkout.total, currency)


def checkout_line_total(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    checkout_line_info: "CheckoutLineInfo",
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
) -> TaxedMoney:
    """Return the total price of provided line, taxes included.

    It takes in account all plugins.
    """
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    currency = checkout_info.checkout.currency
    address = checkout_info.shipping_address or checkout_info.billing_address
    _, lines = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
    )
    checkout_line = find_checkout_line_info(lines, checkout_line_info.line.id).line
    return quantize_price(checkout_line.total_price, currency)


def checkout_line_unit_price(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    checkout_line_info: "CheckoutLineInfo",
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
) -> TaxedMoney:
    """Return the unit price of provided line, taxes included.

    It takes in account all plugins.
    """
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    currency = checkout_info.checkout.currency
    address = checkout_info.shipping_address or checkout_info.billing_address
    _, lines = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
    )
    checkout_line = find_checkout_line_info(lines, checkout_line_info.line.id).line
    unit_price = checkout_line.total_price / checkout_line.quantity
    return quantize_price(unit_price, currency)


def checkout_line_tax_rate(
    *,
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    checkout_line_info: "CheckoutLineInfo",
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> Decimal:
    """Return the tax rate of provided line.

    It takes in account all plugins.
    """
    address = checkout_info.shipping_address or checkout_info.billing_address
    _, lines = fetch_checkout_data(
        checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
    )
    checkout_line_info = find_checkout_line_info(lines, checkout_line_info.line.id)
    return checkout_line_info.line.tax_rate


def checkout_line_undiscounted_unit_price(
    *,
    checkout_info: "CheckoutInfo",
    checkout_line_info: "CheckoutLineInfo",
):
    # Fetch the undiscounted unit price from channel listings in case the prices
    # are invalidated.
    if (
        checkout_info.checkout.price_expiration < timezone.now()
        or checkout_line_info.line.undiscounted_unit_price is None
    ):
        return base_calculations.calculate_undiscounted_base_line_unit_price(
            checkout_line_info, checkout_info.channel
        )
    currency = checkout_info.checkout.currency
    return quantize_price(checkout_line_info.line.undiscounted_unit_price, currency)


def checkout_line_undiscounted_total_price(
    *,
    checkout_info: "CheckoutInfo",
    checkout_line_info: "CheckoutLineInfo",
):
    undiscounted_unit_price = checkout_line_undiscounted_unit_price(
        checkout_info=checkout_info, checkout_line_info=checkout_line_info
    )
    total_price = undiscounted_unit_price * checkout_line_info.line.quantity
    return quantize_price(total_price, total_price.currency)


def update_undiscounted_prices(
    checkout_info: "CheckoutInfo", lines: Iterable["CheckoutLineInfo"]
):
    delivery_method_info = checkout_info.delivery_method_info
    if isinstance(delivery_method_info, ShippingMethodInfo):
        shipping_method_data = delivery_method_info.delivery_method
        checkout_info.checkout.undiscounted_base_shipping_price_amount = (
            shipping_method_data.price.amount
        )
    else:
        checkout_info.checkout.undiscounted_base_shipping_price_amount = Decimal(0)

    _update_undiscounted_unit_price_for_lines(lines)


def _update_undiscounted_unit_price_for_lines(lines: Iterable["CheckoutLineInfo"]):
    """Update line undiscounted unit price amount.

    Undiscounted unit price stores the denormalized price of the variant.
    """
    for line_info in lines:
        if not line_info.channel_listing or line_info.channel_listing.price is None:
            continue

        line_info.line.undiscounted_unit_price = line_info.undiscounted_unit_price


def _fetch_checkout_prices_if_expired(
    checkout_info: "CheckoutInfo",
    manager: "PluginsManager",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
) -> tuple["CheckoutInfo", Iterable["CheckoutLineInfo"]]:
    """Fetch checkout prices with taxes.

    First calculate and apply all checkout prices with taxes separately,
    then apply tax data as well if we receive one.

    Prices can be updated only if force_update == True, or if time elapsed from the
    last price update is greater than settings.CHECKOUT_PRICES_TTL.
    """
    from .utils import checkout_info_for_logs

    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}

    checkout = checkout_info.checkout

    if not force_update and checkout.price_expiration > timezone.now():
        return checkout_info, lines

    _set_checkout_base_prices(checkout, checkout_info, lines)

    checkout_update_fields = [
        "voucher_code",
        "total_net_amount",
        "total_gross_amount",
        "subtotal_net_amount",
        "subtotal_gross_amount",
        "shipping_price_net_amount",
        "shipping_price_gross_amount",
        "undiscounted_base_shipping_price_amount",
        "shipping_tax_rate",
        "translated_discount_name",
        "discount_amount",
        "discount_name",
        "currency",
        "last_change",
        "price_expiration",
        "tax_error",
    ]

    checkout.price_expiration = timezone.now() + settings.CHECKOUT_PRICES_TTL

    from .utils import checkout_lines_bulk_update

    with allow_writer():
        with transaction.atomic():
            checkout.save(
                update_fields=checkout_update_fields,
                using=settings.DATABASE_CONNECTION_DEFAULT_NAME,
            )
            checkout_lines_bulk_update(
                [line_info.line for line_info in lines],
                [
                    "total_price_net_amount",
                    "total_price_gross_amount",
                    "tax_rate",
                    "undiscounted_unit_price_amount",
                ],
            )
    return checkout_info, lines

def _call_plugin_or_tax_app(
    tax_app_identifier: str,
    checkout: "Checkout",
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"] = None,
    pregenerated_subscription_payloads: Optional[dict] = None,
):
    from .utils import log_address_if_validation_skipped_for_checkout

    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}

    if tax_app_identifier.startswith(PLUGIN_IDENTIFIER_PREFIX):
        plugin_ids = [tax_app_identifier.replace(PLUGIN_IDENTIFIER_PREFIX, "")]
        plugins = manager.get_plugins(
            checkout_info.channel.slug,
            active_only=True,
            plugin_ids=plugin_ids,
        )
        if not plugins:
            raise TaxDataError(TaxDataErrorMessage.EMPTY)
        _apply_tax_data_from_plugins(
            checkout,
            manager,
            checkout_info,
            lines,
            address,
            plugin_ids=plugin_ids,
        )
        if checkout.tax_error:
            raise TaxDataError(checkout.tax_error)
    else:
        log_address_if_validation_skipped_for_checkout(checkout_info, logger)


def _calculate_checkout_total(checkout, currency):
    total = checkout.subtotal + checkout.shipping_price
    return quantize_price(
        total,
        currency,
    )


def _calculate_checkout_subtotal(lines, currency):
    line_totals = [line_info.line.total_price for line_info in lines]
    total = sum(line_totals, zero_taxed_money(currency))
    return quantize_price(
        total,
        currency,
    )


def _apply_tax_data(
    checkout: "Checkout",
    lines: Iterable["CheckoutLineInfo"],
    tax_data: Optional[TaxData],
) -> None:
    if not tax_data:
        return

    currency = checkout.currency
    for line_info, tax_line_data in zip(lines, tax_data.lines):
        line = line_info.line

        line.total_price = quantize_price(
            TaxedMoney(
                net=Money(tax_line_data.total_net_amount, currency),
                gross=Money(tax_line_data.total_gross_amount, currency),
            ),
            currency,
        )

    checkout.shipping_price = quantize_price(
        TaxedMoney(
            net=Money(tax_data.shipping_price_net_amount, currency),
            gross=Money(tax_data.shipping_price_gross_amount, currency),
        ),
        currency,
    )
    checkout.subtotal = _calculate_checkout_subtotal(lines, currency)
    checkout.total = _calculate_checkout_total(checkout, currency)


def _apply_tax_data_from_plugins(
    checkout: "Checkout",
    manager: "PluginsManager",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"],
    plugin_ids: Optional[list[str]] = None,
) -> None:
    for line_info in lines:
        line = line_info.line

        total_price = manager.calculate_checkout_line_total(
            checkout_info,
            lines,
            line_info,
            address,
            plugin_ids=plugin_ids,
        )
        line.total_price = total_price

        line.tax_rate = manager.get_checkout_line_tax_rate(
            checkout_info,
            lines,
            line_info,
            address,
            total_price,
            plugin_ids=plugin_ids,
        )

    checkout.shipping_price = manager.calculate_checkout_shipping(
        checkout_info, lines, address, plugin_ids=plugin_ids
    )
    checkout.shipping_tax_rate = manager.get_checkout_shipping_tax_rate(
        checkout_info, lines, address, checkout.shipping_price, plugin_ids=plugin_ids
    )
    checkout.subtotal = manager.calculate_checkout_subtotal(
        checkout_info, lines, address, plugin_ids=plugin_ids
    )
    checkout.total = manager.calculate_checkout_total(
        checkout_info,
        lines,
        address,
        plugin_ids=plugin_ids,
    )


def _set_checkout_base_prices(
    checkout: "Checkout",
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
) -> None:
    currency = checkout_info.checkout.currency
    subtotal = zero_money(currency)

    for line_info in lines:
        line = line_info.line
        total_price = (
            base_calculations.get_line_total_price_with_propagated_checkout_discount(
                checkout_info, lines, line_info
            )
        )
        line_total_price = quantize_price(total_price, currency)
        subtotal += line_total_price

        line.total_price = TaxedMoney(net=line_total_price, gross=line_total_price)

        # Set zero tax rate since net and gross are equal.
        line.tax_rate = Decimal("0.0")

    # Calculate shipping price
    shipping_price = base_calculations.base_checkout_delivery_price(
        checkout_info, lines
    )
    checkout.shipping_price = quantize_price(
        TaxedMoney(shipping_price, shipping_price), currency
    )
    checkout.shipping_tax_rate = Decimal("0.0")

    # Set subtotal
    checkout.subtotal = TaxedMoney(net=subtotal, gross=subtotal)

    # Calculate checkout total
    total = subtotal + shipping_price
    checkout.total = quantize_price(TaxedMoney(net=total, gross=total), currency)


def fetch_checkout_data(
    checkout_info: "CheckoutInfo",
    manager: "PluginsManager",
    lines: Iterable["CheckoutLineInfo"],
    address: Optional["Address"] = None,
    force_update: bool = False,
    checkout_transactions: Optional[Iterable["TransactionItem"]] = None,
    force_status_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
    pregenerated_subscription_payloads: Optional[dict] = None,
):
    """Fetch checkout data.

    This function refreshes prices if they have expired. If the checkout total has
    changed as a result, it will update the payment statuses accordingly.
    """
    if pregenerated_subscription_payloads is None:
        pregenerated_subscription_payloads = {}
    previous_total_gross = checkout_info.checkout.total.gross
    checkout_info, lines = _fetch_checkout_prices_if_expired(
        checkout_info=checkout_info,
        manager=manager,
        lines=lines,
        address=address,
        force_update=force_update,
        database_connection_name=database_connection_name,
        pregenerated_subscription_payloads=pregenerated_subscription_payloads,
    )
    current_total_gross = checkout_info.checkout.total.gross
    if current_total_gross != previous_total_gross or force_status_update:
        update_checkout_payment_statuses(
            checkout=checkout_info.checkout,
            checkout_total_gross=current_total_gross,
            checkout_has_lines=bool(lines),
            checkout_transactions=checkout_transactions,
            database_connection_name=database_connection_name,
        )

    return checkout_info, lines
