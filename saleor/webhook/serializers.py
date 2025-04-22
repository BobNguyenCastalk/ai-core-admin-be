from typing import TYPE_CHECKING

from prices import Money

from ..core.prices import quantize_price

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from ..checkout.models import Checkout


def serialize_checkout_lines(checkout: "Checkout") -> list[dict]:
    data = []
    channel = checkout.channel
    currency = channel.currency_code
    lines, _ = [], []
    for line_info in lines:
        variant = line_info.variant
        product = variant.product
        base_price = line_info.undiscounted_unit_price
        total_discount_amount_for_line = 0
        if total_discount_amount_for_line:
            unit_discount_amount = (
                total_discount_amount_for_line / line_info.line.quantity
            )
            unit_discount = Money(unit_discount_amount, currency)
            unit_discount = quantize_price(unit_discount, currency)
            base_price -= unit_discount
        data.append(
            {
                "sku": variant.sku,
                "variant_id": variant.get_global_id(),
                "quantity": line_info.line.quantity,
                "base_price": str(quantize_price(base_price.amount, currency)),
                "currency": currency,
                "full_name": variant.display_product(),
                "product_name": product.name,
                "variant_name": variant.name,
                "attributes": serialize_variant_attributes(variant),
            }
        )
    return data
