import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import prefetch_related_objects
from prices import  TaxedMoney

from ..core.db.connection import allow_writer
from ..core.prices import quantize_price
from ..plugins.manager import PluginsManager
from . import ORDER_EDITABLE_STATUS
from .base_calculations import apply_order_discounts
from .fetch import EditableOrderLineInfo, fetch_draft_order_lines_info
from .interface import OrderTaxedPricesData
from .models import Order, OrderLine

logger = logging.getLogger(__name__)


def fetch_order_prices_if_expired(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> tuple[Order, Optional[Iterable[OrderLine]]]:
    """Fetch order prices with taxes.

    First applies order level discounts, then calculates taxes.

    Prices will be updated if force_update is True
    or if order.should_refresh_prices is True.
    """
    if order.status not in ORDER_EDITABLE_STATUS:
        return order, lines

    if not force_update and not order.should_refresh_prices:
        return order, lines

    # handle promotions
    lines_info: list[EditableOrderLineInfo] = fetch_draft_order_lines_info(order, lines)
    lines = [line_info.line for line_info in lines_info]

    _clear_prefetched_discounts(order, lines)
    with allow_writer():
        # TODO: Load discounts with a dataloader and pass as argument
        prefetch_related_objects([order], "discounts")

    # handle taxes
    _recalculate_prices(
        order,
        manager,
        lines,
        database_connection_name=database_connection_name,
    )

    order.should_refresh_prices = False
    with transaction.atomic(savepoint=False):
        with allow_writer():
            order.save(
                update_fields=[
                    "subtotal_net_amount",
                    "subtotal_gross_amount",
                    "total_net_amount",
                    "total_gross_amount",
                    "undiscounted_total_net_amount",
                    "undiscounted_total_gross_amount",
                    "shipping_price_net_amount",
                    "shipping_price_gross_amount",
                    "base_shipping_price_amount",
                    "shipping_tax_rate",
                    "should_refresh_prices",
                    "tax_error",
                ]
            )
            order.lines.bulk_update(
                lines,
                [
                    "unit_price_net_amount",
                    "unit_price_gross_amount",
                    "undiscounted_unit_price_net_amount",
                    "undiscounted_unit_price_gross_amount",
                    "total_price_net_amount",
                    "total_price_gross_amount",
                    "undiscounted_total_price_net_amount",
                    "undiscounted_total_price_gross_amount",
                    "tax_rate",
                    "unit_discount_amount",
                    "unit_discount_reason",
                    "unit_discount_type",
                    "unit_discount_value",
                    "base_unit_price_amount",
                ],
            )

        return order, lines


def _clear_prefetched_discounts(order, lines):
    if hasattr(order, "_prefetched_objects_cache"):
        order._prefetched_objects_cache.pop("discounts", None)

    for line in lines:
        if hasattr(line, "_prefetched_objects_cache"):
            line._prefetched_objects_cache.pop("discounts", None)


def _recalculate_prices(
    order: Order,
    manager: PluginsManager,
    lines: Iterable[OrderLine],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
):
    """Calculate prices after handling order level discounts and taxes."""

    apply_order_discounts(
        order,
        lines,
        database_connection_name=database_connection_name,
    )

def _find_order_line(
    lines: Optional[Iterable[OrderLine]],
    order_line: OrderLine,
) -> OrderLine:
    """Return order line from provided lines.

    The return value represents the updated version of order_line parameter.
    """
    return next(
        (line for line in (lines or []) if line.pk == order_line.pk), order_line
    )


def order_line_unit(
    order: Order,
    order_line: OrderLine,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> OrderTaxedPricesData:
    """Return the unit price of provided line, taxes included.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    _, lines = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    order_line = _find_order_line(lines, order_line)
    return OrderTaxedPricesData(
        undiscounted_price=quantize_price(order_line.undiscounted_unit_price, currency),
        price_with_discounts=quantize_price(order_line.unit_price, currency),
    )


def order_line_total(
    order: Order,
    order_line: OrderLine,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> OrderTaxedPricesData:
    """Return the total price of provided line, taxes included.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    _, lines = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    order_line = _find_order_line(lines, order_line)
    return OrderTaxedPricesData(
        undiscounted_price=quantize_price(
            order_line.undiscounted_total_price, currency
        ),
        price_with_discounts=quantize_price(order_line.total_price, currency),
    )


def order_line_tax_rate(
    order: Order,
    order_line: OrderLine,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> Optional[Decimal]:
    """Return the tax rate of provided line.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    _, lines = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    order_line = _find_order_line(lines, order_line)
    return order_line.tax_rate


def order_line_unit_discount(
    order: Order,
    order_line: OrderLine,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
) -> Decimal:
    """Return the line unit discount.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.

    Line unit discount includes discounts from:
    - catalogue promotion
    - voucher applied on the line (`SPECIFIC_PRODUCT`, `apply_once_per_order` )
    - manual line discounts
    """
    _, lines = fetch_order_prices_if_expired(order, manager, lines, force_update)
    order_line = _find_order_line(lines, order_line)
    return order_line.unit_discount


def order_line_unit_discount_value(
    order: Order,
    order_line: OrderLine,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
) -> Decimal:
    """Return the line unit discount value.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    _, lines = fetch_order_prices_if_expired(order, manager, lines, force_update)
    order_line = _find_order_line(lines, order_line)
    return order_line.unit_discount_value


def order_line_unit_discount_type(
    order: Order,
    order_line: OrderLine,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
) -> Optional[str]:
    """Return the line unit discount type.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    _, lines = fetch_order_prices_if_expired(order, manager, lines, force_update)
    order_line = _find_order_line(lines, order_line)
    return order_line.unit_discount_type


def order_undiscounted_shipping(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> TaxedMoney:
    """Return the undiscounted shipping price of the order.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    order, _ = fetch_order_prices_if_expired(
        order, manager, lines, force_update, database_connection_name
    )
    return quantize_price(order.undiscounted_base_shipping_price, currency)


def order_shipping(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> TaxedMoney:
    """Return the shipping price of the order.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    order, _ = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    return quantize_price(order.shipping_price, currency)


def order_shipping_tax_rate(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> Optional[Decimal]:
    """Return the shipping tax rate of the order.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    order, _ = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    return order.shipping_tax_rate


def order_subtotal(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
):
    """Return the total price of the order.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    order, lines = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    # Lines aren't returned only if
    # we don't pass them to `fetch_order_prices_if_expired`.
    return quantize_price(order.subtotal, currency)


def order_total(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> TaxedMoney:
    """Return the total price of the order.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    order, _ = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    return quantize_price(order.total, currency)


def order_undiscounted_total(
    order: Order,
    manager: PluginsManager,
    lines: Optional[Iterable[OrderLine]] = None,
    force_update: bool = False,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> TaxedMoney:
    """Return the undiscounted total price of the order.

    It takes into account all plugins.
    If the prices are expired, call all order price calculation methods
    and save them in the model directly.
    """
    currency = order.currency
    order, _ = fetch_order_prices_if_expired(
        order,
        manager,
        lines,
        force_update,
        database_connection_name=database_connection_name,
    )
    return quantize_price(order.undiscounted_total, currency)
