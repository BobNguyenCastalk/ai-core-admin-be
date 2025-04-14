"""Checkout-related utility functions."""

from collections.abc import Iterable
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union, cast
from uuid import UUID

import graphene
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..account.models import User
from ..checkout.fetch import update_delivery_method_lists_for_checkout_info
from ..core.db.connection import allow_writer
from ..core.exceptions import NonExistingCheckoutLines, ProductNotPublished
from ..core.taxes import zero_taxed_money
from ..core.weight import zero_weight
from ..payment.models import Payment
from ..plugins.manager import PluginsManager
from ..product import models as product_models
from . import AddressType, calculations
from .error_codes import CheckoutErrorCode
from .models import Checkout, CheckoutLine, CheckoutMetadata

if TYPE_CHECKING:
    from measurement.measures import Weight

    from ..account.models import Address
    from ..core.pricing.interface import LineInfo
    from ..order.models import Order, OrderLine
    from .fetch import CheckoutInfo, CheckoutLineInfo


PRIVATE_META_APP_SHIPPING_ID = "external_app_shipping_id"


def checkout_lines_qs_select_for_update():
    return CheckoutLine.objects.order_by("id").select_for_update(of=(["self"]))


def checkout_lines_bulk_update(
    lines_to_update: list["CheckoutLine"], fields_to_update: list[str]
):
    """Bulk update on CheckoutLines with lock applied on them."""
    with transaction.atomic():
        _locked_lines = list(
            checkout_lines_qs_select_for_update()
            .filter(id__in=[line.id for line in lines_to_update])
            .values_list("id", flat=True)
        )
        CheckoutLine.objects.bulk_update(lines_to_update, fields_to_update)


def checkout_lines_bulk_delete(line_pks_to_delete: list[UUID]):
    """Delete CheckoutLines with lock applied on them."""
    with transaction.atomic():
        CheckoutLine.objects.filter(
            id__in=checkout_lines_qs_select_for_update()
            .filter(pk__in=line_pks_to_delete)
            .values_list("id", flat=True)
        ).delete()


def delete_checkouts(checkout_pks_to_delete: list[UUID]) -> int:
    """Delete a checouts with lock applied on them."""
    with transaction.atomic():
        CheckoutLine.objects.filter(
            id__in=CheckoutLine.objects.order_by("id")
            .select_for_update()
            .filter(checkout_id__in=checkout_pks_to_delete)
            .values_list("id", flat=True)
        ).delete()
        deleted_count, _ = Checkout.objects.filter(
            pk__in=checkout_pks_to_delete
        ).delete()
    return deleted_count


def get_user_checkout(
    user: User,
    checkout_queryset=None,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
) -> Optional[Checkout]:
    if not checkout_queryset:
        checkout_queryset = Checkout.objects.using(database_connection_name).all()
    return checkout_queryset.filter(user=user, channel__is_active=True).first()


def check_variant_in_stock(
    checkout: Checkout,
    variant: product_models.ProductVariant,
    channel_slug: str,
    quantity: int = 1,
    replace: bool = False,
    check_quantity: bool = True,
    checkout_lines: Optional[list["CheckoutLine"]] = None,
    check_reservations: bool = False,
) -> tuple[int, Optional[CheckoutLine]]:
    """Check if a given variant is in stock and return the new quantity + line."""
    line = checkout.lines.filter(variant=variant).first()
    line_quantity = 0 if line is None else line.quantity

    new_quantity = quantity if replace else (quantity + line_quantity)

    if new_quantity < 0:
        raise ValueError(
            f"{quantity!r} is not a valid quantity (results in {new_quantity!r})"
        )

    return new_quantity, line


def add_variant_to_checkout(
    checkout_info: "CheckoutInfo",
    variant: product_models.ProductVariant,
    quantity: int = 1,
    price_override: Optional["Decimal"] = None,
    replace: bool = False,
    check_quantity: bool = True,
    force_new_line: bool = False,
):
    """Add a product variant to checkout.

    If `replace` is truthy then any previous quantity is discarded instead
    of added to.

    This function is not used outside of test suite.
    """
    checkout = checkout_info.checkout
    channel_slug = checkout_info.channel.slug

    product_channel_listing = product_models.ProductChannelListing.objects.filter(
        channel_id=checkout.channel_id, product_id=variant.product_id
    ).first()
    if not product_channel_listing or not product_channel_listing.is_published:
        raise ProductNotPublished()

    variant_channel_listing = product_models.ProductVariantChannelListing.objects.get(
        channel_id=checkout.channel_id, variant_id=variant.id
    )
    variant_price_amount = variant.get_base_price(
        variant_channel_listing, price_override
    ).amount

    new_quantity, line = check_variant_in_stock(
        checkout,
        variant,
        channel_slug,
        quantity=quantity,
        replace=replace,
        check_quantity=check_quantity,
    )

    if force_new_line:
        checkout.lines.create(
            variant=variant,
            quantity=quantity,
            price_override=price_override,
            undiscounted_unit_price_amount=variant_price_amount,
        )
        return checkout

    if line is None:
        line = checkout.lines.filter(variant=variant).first()

    if new_quantity == 0:
        if line is not None:
            line.delete()
    elif line is None:
        checkout.lines.create(
            variant=variant,
            quantity=new_quantity,
            currency=checkout.currency,
            price_override=price_override,
            undiscounted_unit_price_amount=variant_price_amount,
        )
    elif new_quantity > 0:
        line.quantity = new_quantity
        line.save(update_fields=["quantity"])

    # invalidate calculated prices
    checkout.price_expiration = timezone.now()
    return checkout


def calculate_checkout_quantity(lines: Iterable["CheckoutLineInfo"]):
    return sum([line_info.line.quantity for line_info in lines])


def add_variants_to_checkout(
    checkout,
    variants,
    checkout_lines_data,
    channel,
    replace=False,
    replace_reservations=False,
    reservation_length: Optional[int] = None,
    raise_error_for_missing_lines=False,
):
    """Add variants to checkout.

    If a variant is not placed in checkout, a new checkout line will be created.
    If quantity is set to 0, checkout line will be deleted.
    Otherwise, quantity will be added or replaced (if replace argument is True).
    When `raise_error_for_missing_lines` is set to True, raise error when any line from
    the input is not assigned to provided checkout.
    """
    country_code = checkout.get_country()
    with transaction.atomic():
        checkout_lines = list(
            checkout_lines_qs_select_for_update()
            .select_related("variant")
            .filter(checkout_id=checkout.pk)
        )
        lines_by_id = {str(line.pk): line for line in checkout_lines}
        variants_map = {str(variant.pk): variant for variant in variants}

        new_variant_ids = set()
        non_existing_line_ids = set()
        for line_data in checkout_lines_data:
            if line_data.line_id and line_data.line_id not in lines_by_id:
                non_existing_line_ids.add(line_data.line_id)
                new_variant_ids.add(line_data.variant_id)
            elif not line_data.line_id and line_data.variant_id:
                new_variant_ids.add(line_data.variant_id)

        if raise_error_for_missing_lines and non_existing_line_ids:
            raise NonExistingCheckoutLines(non_existing_line_ids)

        new_variant_listing_map = {
            listing.variant_id: listing
            for listing in product_models.ProductVariantChannelListing.objects.filter(
                channel_id=channel.id, variant_id__in=new_variant_ids
            )
        }

        to_create: list[CheckoutLine] = []
        to_update: list[CheckoutLine] = []
        to_delete: list[CheckoutLine] = []

        for line_data in checkout_lines_data:
            line = lines_by_id.get(line_data.line_id) if line_data.line_id else None
            if line:
                _append_line_to_update(to_update, to_delete, line_data, replace, line)
                _append_line_to_delete(to_delete, line_data, line)
            else:
                variant = variants_map[line_data.variant_id]
                _append_line_to_create(
                    to_create, checkout, variant, line_data, new_variant_listing_map
                )

        if to_delete:
            checkout_lines_bulk_delete([line.pk for line in to_delete])

        if to_update:
            checkout_lines_bulk_update(
                to_update, ["quantity", "price_override", "metadata"]
            )

        if to_create:
            CheckoutLine.objects.bulk_create(to_create)

        to_reserve = to_create + to_update

        if reservation_length and to_reserve:
            updated_lines_ids = [line.pk for line in to_reserve + to_delete]

            # Validation for stock reservation should be performed on new and updated lines.
            # For already existing lines only reserved_until should be updated.
            lines_to_update_reservation_time = []
            for line in checkout_lines:
                if line.pk not in updated_lines_ids:
                    lines_to_update_reservation_time.append(line)

    return checkout


def _get_line_if_exist(line_data, lines_by_ids):
    if line_data.line_id and line_data.line_id in lines_by_ids:
        return lines_by_ids[line_data.line_id]


def _append_line_to_update(to_update, to_delete, line_data, replace, line):
    if line_data.metadata_list:
        line.store_value_in_metadata(
            {data.key: data.value for data in line_data.metadata_list}
        )
    if line_data.quantity_to_update:
        quantity = line_data.quantity
        if quantity > 0:
            if replace:
                line.quantity = quantity
            else:
                line.quantity += quantity
            to_update.append(line)
    if line_data.custom_price_to_update:
        if line not in to_delete:
            line.price_override = line_data.custom_price
            to_update.append(line)


def _append_line_to_delete(to_delete, line_data, line):
    quantity = line_data.quantity
    if line_data.quantity_to_update:
        if quantity <= 0:
            to_delete.append(line)


def _append_line_to_create(
    to_create,
    checkout,
    variant,
    line_data,
    new_variant_listing_map: dict[int, "product_models.ProductVariantChannelListing"],
):
    if line_data.quantity > 0:
        variant_price_amount = variant.get_base_price(
            new_variant_listing_map.get(variant.id), line_data.custom_price
        ).amount
        checkout_line = CheckoutLine(
            checkout=checkout,
            variant=variant,
            quantity=line_data.quantity,
            currency=checkout.currency,
            price_override=line_data.custom_price,
            undiscounted_unit_price_amount=variant_price_amount,
        )
        if line_data.metadata_list:
            checkout_line.store_value_in_metadata(
                {data.key: data.value for data in line_data.metadata_list}
            )
        to_create.append(checkout_line)


def _check_new_checkout_address(checkout, address, address_type):
    """Check if and address in checkout has changed and if to remove old one."""
    if address_type == AddressType.BILLING:
        old_address = checkout.billing_address
    else:
        old_address = checkout.shipping_address

    has_address_changed = any(
        [
            not address and old_address,
            address and not old_address,
            address and old_address and address != old_address,
        ]
    )

    remove_old_address = (
        has_address_changed
        and old_address is not None
        and (not checkout.user or old_address not in checkout.user.addresses.all())
    )

    return has_address_changed, remove_old_address


def change_billing_address_in_checkout(checkout, address) -> list[str]:
    """Save billing address in checkout if changed.

    Remove previously saved address if not connected to any user.
    This function does not save anything to database and
    instead returns updated fields.
    """
    changed, remove = _check_new_checkout_address(
        checkout, address, AddressType.BILLING
    )
    updated_fields = []
    if changed:
        if remove:
            checkout.billing_address.delete()
        checkout.billing_address = address
        updated_fields = ["billing_address", "last_change"]
    return updated_fields


def change_shipping_address_in_checkout(
    checkout_info: "CheckoutInfo",
    address: "Address",
    lines: Iterable["CheckoutLineInfo"],
    manager: "PluginsManager",
    shipping_channel_listings: Iterable,
):
    """Save shipping address in checkout if changed.

    Remove previously saved address if not connected to any user.
    This function does not save anything to database and
    instead returns updated fields.
    """
    checkout = checkout_info.checkout
    changed, remove = _check_new_checkout_address(
        checkout, address, AddressType.SHIPPING
    )
    updated_fields = []
    if changed:
        if remove and checkout.shipping_address:
            checkout.shipping_address.delete()
        checkout.shipping_address = address
        update_delivery_method_lists_for_checkout_info(
            checkout_info=checkout_info,
            shipping_method=checkout_info.checkout.shipping_method,
            collection_point=checkout_info.checkout.collection_point,
            shipping_address=address,
            lines=lines,
            shipping_channel_listings=shipping_channel_listings,
        )
        updated_fields = ["shipping_address", "last_change"]
    return updated_fields


def get_base_lines_prices(
    lines: Iterable["LineInfo"],
):
    """Get base total price of checkout lines without voucher discount applied."""
    return [
        line_info.variant_discounted_price
        for line_info in lines
        for i in range(line_info.line.quantity)
    ]


def get_valid_collection_points_for_checkout(
    lines: Iterable["CheckoutLineInfo"],
    channel_id: int,
    quantity_check: bool = True,
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
):
    """Return a collection of `Warehouse`s that can be used as a collection point.

    Note that `quantity_check=False` should be used, when stocks quantity will
    be validated in further steps (checkout completion) in order to raise
    'InsufficientProductStock' error instead of 'InvalidShippingError'.
    """
    if not is_shipping_required(lines):
        return []

    line_ids = [line_info.line.id for line_info in lines]
    lines = CheckoutLine.objects.using(database_connection_name).filter(id__in=line_ids)

    return []


def clear_delivery_method(
    checkout_info: "CheckoutInfo", save: bool = True
) -> list[str]:
    checkout = checkout_info.checkout
    checkout.collection_point = None
    checkout.shipping_method = None
    checkout.shipping_method_name = None
    checkout_info.shipping_method = None

    update_delivery_method_lists_for_checkout_info(
        checkout_info=checkout_info,
        shipping_method=None,
        collection_point=None,
        shipping_address=checkout_info.shipping_address,
        lines=checkout_info.lines,
        shipping_channel_listings=checkout_info.shipping_channel_listings,
    )

    remove_external_shipping(checkout=checkout)
    update_fields = [
        "shipping_method",
        "collection_point",
        "last_change",
        "shipping_method_name",
        "external_shipping_method_id",
    ]
    if save:
        checkout.save(update_fields=update_fields)
    get_checkout_metadata(checkout).save()
    return update_fields


def is_fully_paid(
    manager: PluginsManager,
    checkout_info: "CheckoutInfo",
    lines: Iterable["CheckoutLineInfo"],
    database_connection_name: str = settings.DATABASE_CONNECTION_DEFAULT_NAME,
):
    """Check if provided payment methods cover the checkout's total amount.

    Note that these payments may not be captured or charged at all.
    """
    checkout = checkout_info.checkout
    payments = [payment for payment in checkout.payments.all() if payment.is_active]
    total_paid = sum([p.total for p in payments])
    address = checkout_info.shipping_address or checkout_info.billing_address
    checkout_total = calculations.calculate_checkout_total_with_gift_cards(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=address,
        database_connection_name=database_connection_name,
    )
    checkout_total = max(
        checkout_total, zero_taxed_money(checkout_total.currency)
    ).gross
    return total_paid >= checkout_total.amount


def cancel_active_payments(checkout: Checkout) -> list[int]:
    payments = checkout.payments.filter(is_active=True)
    payment_ids = list(payments.values_list("id", flat=True))
    payments.update(is_active=False)
    return payment_ids


def activate_payments(payment_ids: list[int]) -> None:
    Payment.objects.filter(id__in=payment_ids).update(is_active=True)


def is_shipping_required(lines: Iterable["CheckoutLineInfo"]):
    """Check if shipping is required for given checkout lines."""
    return any(line_info.product_type.is_shipping_required for line_info in lines)


def validate_variants_in_checkout_lines(lines: Iterable["CheckoutLineInfo"]):
    variants_listings_map = {line.variant.id: line.channel_listing for line in lines}

    not_available_variants = [
        variant_id
        for variant_id, channel_listing in variants_listings_map.items()
        if channel_listing is None or channel_listing.price is None
    ]
    if not_available_variants:
        not_available_variants_ids = {
            graphene.Node.to_global_id("ProductVariant", pk)
            for pk in not_available_variants
        }
        error_code = CheckoutErrorCode.UNAVAILABLE_VARIANT_IN_CHANNEL.value
        raise ValidationError(
            {
                "lines": ValidationError(
                    "Cannot add lines with unavailable variants.",
                    code=error_code,
                    params={"variants": not_available_variants_ids},
                )
            }
        )


def set_external_shipping(
    checkout: Checkout, external_shipping_method_data
):
    checkout.external_shipping_method_id = external_shipping_method_data.id
    checkout.shipping_method_name = external_shipping_method_data.name
    metadata = get_or_create_checkout_metadata(checkout)
    metadata.store_value_in_private_metadata(
        {PRIVATE_META_APP_SHIPPING_ID: external_shipping_method_data.id}
    )


def get_external_shipping_id(container: Union["Checkout", "Order"]):
    if type(container) == Checkout:
        if container.external_shipping_method_id:
            return container.external_shipping_method_id
        container = get_checkout_metadata(container)
    return container.get_value_from_private_metadata(  # type:ignore
        PRIVATE_META_APP_SHIPPING_ID
    )


def remove_external_shipping(checkout: Checkout, save: bool = False):
    if checkout.external_shipping_method_id:
        checkout.external_shipping_method_id = None
        checkout.shipping_method_name = None
        if save:
            checkout.save(
                update_fields=[
                    "external_shipping_method_id",
                    "shipping_method_name",
                    "last_change",
                ]
            )
    metadata = get_or_create_checkout_metadata(checkout)
    metadata.delete_value_from_private_metadata(PRIVATE_META_APP_SHIPPING_ID)
    if save:
        metadata.save(update_fields=["private_metadata"])


@allow_writer()
def get_or_create_checkout_metadata(checkout: "Checkout") -> CheckoutMetadata:
    if hasattr(checkout, "metadata_storage"):
        return checkout.metadata_storage
    metadata, _ = CheckoutMetadata.objects.get_or_create(checkout=checkout)
    return metadata


@allow_writer()
def get_checkout_metadata(checkout: "Checkout"):
    if hasattr(checkout, "metadata_storage"):
        # TODO: load metadata_storage with dataloader and pass as an argument
        return checkout.metadata_storage
    else:
        return CheckoutMetadata(checkout=checkout)


def calculate_checkout_weight(lines: Iterable["CheckoutLineInfo"]) -> "Weight":
    weights = zero_weight()
    for checkout_line_info in lines:
        variant = checkout_line_info.variant
        if variant:
            line_weight = get_checkout_line_weight(checkout_line_info)
            weights += line_weight * checkout_line_info.line.quantity
    return weights


def get_checkout_line_weight(line_info: "CheckoutLineInfo"):
    return (
        line_info.variant.weight
        or line_info.product.weight
        or line_info.product_type.weight
    )


def log_address_if_validation_skipped_for_checkout(
    checkout_info: "CheckoutInfo", logger
):
    address = get_address_for_checkout_taxes(checkout_info)
    if address and address.validation_skipped:
        logger.warning(
            "Fetching tax data for checkout with address validation skipped. "
            "Address ID: %s",
            address.id,
        )


def get_address_for_checkout_taxes(
    checkout_info: "CheckoutInfo",
) -> Optional["Address"]:
    shipping_address = checkout_info.delivery_method_info.shipping_address
    return shipping_address or checkout_info.billing_address


def checkout_info_for_logs(
    checkout_info: "CheckoutInfo",
    checkout_lines_info: Iterable["CheckoutLineInfo"],
):
    checkout = checkout_info.checkout
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)
    tax_configuration = checkout_info.tax_configuration
    channel = checkout.channel

    return {
        "checkout_id": checkout_id,
        "checkoutId": checkout_id,
        "checkout": {
            "currency": checkout.currency,
            "total_net_amount": checkout.total_net_amount,
            "total_gross_amount": checkout.total_gross_amount,
            "base_total_amount": checkout.base_total_amount,
            "subtotal_net_amount": checkout.subtotal_net_amount,
            "subtotal_gross_amount": checkout.subtotal_gross_amount,
            "base_subtotal_amount": checkout.base_subtotal_amount,
            "shipping_price_net_amount": checkout.shipping_price_net_amount,
            "shipping_price_gross_amount": checkout.shipping_price_gross_amount,
            "discount_amount": checkout.discount_amount,
            "has_voucher_code": bool(checkout.voucher_code),
            "tax_exemption": checkout.tax_exemption,
            "tax_error": checkout.tax_error,
        },
        "tax_configuration": {
            "charge_taxes": tax_configuration.charge_taxes,
            "tax_calculation_strategy": tax_configuration.tax_calculation_strategy,
            "prices_entered_with_tax": tax_configuration.prices_entered_with_tax,
            "tax_app_id": tax_configuration.tax_app_id,
        },
        "lines": [
            {
                "id": graphene.Node.to_global_id("CheckoutLine", line_info.line.pk),
                "variant_id": graphene.Node.to_global_id(
                    "ProductVariant", line_info.line.variant_id
                ),
                "quantity": line_info.line.quantity,
                "is_gift": line_info.line.is_gift,
                "price_override": line_info.line.price_override,
                "total_price_net_amount": line_info.line.total_price_net_amount,
                "total_price_gross_amount": line_info.line.total_price_gross_amount,
                "variant_listing_price": (
                    line_info.channel_listing.price_amount
                    if line_info.channel_listing
                    else None
                ),
                "variant_listing_discounted_price": (
                    line_info.channel_listing.discounted_price_amount
                    if line_info.channel_listing
                    else None
                ),
                "undiscounted_unit_price_amount": line_info.line.undiscounted_unit_price_amount,
                "product_listing_discounted_price": (
                    line_info.product.channel_listings.get(
                        channel=channel
                    ).discounted_price_amount
                    if line_info.product.channel_listings
                    else None
                ),
                "product_discounted_price_dirty": (
                    line_info.product.channel_listings.get(
                        channel=channel
                    ).discounted_price_dirty
                    if line_info.product.channel_listings
                    else None
                ),
            }
            for line_info in checkout_lines_info
        ],
    }


def log_unknown_discount_reason(
    order_lines: Iterable["OrderLine"],
    checkout_info: "CheckoutInfo",
    checkout_lines_info: Iterable["CheckoutLineInfo"],
    logger,
):
    prices_entered_with_tax = checkout_info.tax_configuration.prices_entered_with_tax
    for line in order_lines:
        discount_price = line.undiscounted_unit_price - line.unit_price
        if prices_entered_with_tax:
            discount_amount = discount_price.gross
        else:
            discount_amount = discount_price.net
        if discount_amount.amount > 0 and not line.unit_discount_reason:
            logger.warning(
                "Unknown discount reason",
                extra=checkout_info_for_logs(checkout_info, checkout_lines_info),
            )
            return
