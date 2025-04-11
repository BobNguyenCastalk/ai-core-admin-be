from functools import partial
from typing import Union

import graphene
from prices import Money
from promise import Promise

from ....checkout import base_calculations
from ....checkout.models import Checkout, CheckoutLine
from ....core.prices import quantize_price
from ....discount import DiscountType
from ....discount.utils.checkout import has_checkout_order_promotion
from ....discount.utils.manual_discount import split_manual_discount
from ....discount.utils.voucher import is_order_level_voucher
from ....order.base_calculations import base_order_subtotal
from ....order.models import Order, OrderLine
from ...account.dataloaders import AddressByIdLoader
from ...channel.dataloaders import ChannelByIdLoader
from ...channel.types import Channel
from ...checkout import types as checkout_types
from ...checkout.dataloaders import (
    CheckoutByTokenLoader,
    CheckoutInfoByCheckoutTokenLoader,
    CheckoutLinesByCheckoutTokenLoader,
    CheckoutLinesInfoByCheckoutTokenLoader,
)
from ...core.doc_category import DOC_CATEGORY_TAXES
from ...core.types import BaseObjectType
from ...discount.dataloaders import OrderDiscountsByOrderIDLoader
from ...order import types as order_types
from ...order.dataloaders import OrderByIdLoader, OrderLinesByOrderIdLoader
from ...product.dataloaders.products import (
    ProductByVariantIdLoader,
    ProductVariantByIdLoader,
)
from .. import ResolveInfo
from .common import NonNullList
from .money import Money as MoneyType
from .order_or_checkout import OrderOrCheckoutBase


class TaxSourceObject(OrderOrCheckoutBase):
    class Meta:
        types = OrderOrCheckoutBase.get_types()


class TaxSourceLine(graphene.Union):
    class Meta:
        types = (checkout_types.CheckoutLine, order_types.OrderLine)

    @classmethod
    def resolve_type(cls, instance, info: ResolveInfo):
        if isinstance(instance, CheckoutLine):
            return checkout_types.CheckoutLine
        if isinstance(instance, OrderLine):
            return order_types.OrderLine
        return super().resolve_type(instance, info)


class TaxableObjectLine(BaseObjectType):
    source_line = graphene.Field(
        TaxSourceLine,
        required=True,
        description="The source line related to this tax line.",
    )
    quantity = graphene.Int(required=True, description="Number of items.")
    charge_taxes = graphene.Boolean(
        required=True,
        description="Determines if taxes are being charged for the product.",
    )
    product_name = graphene.String(description="The product name.", required=True)
    variant_name = graphene.String(description="The variant name.", required=True)
    product_sku = graphene.String(description="The product sku.")

    unit_price = graphene.Field(
        MoneyType,
        description=(
            "Price of the single item in the order line. "
            "The price includes catalogue promotions, specific product "
            "and applied once per order voucher discounts. "
            "The price does not include the entire order discount."
        ),
        required=True,
    )
    total_price = graphene.Field(
        MoneyType,
        description=(
            "Price of the order line. "
            "The price includes catalogue promotions, specific product "
            "and applied once per order voucher discounts. "
            "The price does not include the entire order discount."
        ),
        required=True,
    )

    class Meta:
        doc_category = DOC_CATEGORY_TAXES

    @staticmethod
    def resolve_variant_name(root: Union[CheckoutLine, OrderLine], info: ResolveInfo):
        if isinstance(root, CheckoutLine):

            def get_name(variant):
                return variant.name

            if not root.variant_id:
                return ""
            return (
                ProductVariantByIdLoader(info.context)
                .load(root.variant_id)
                .then(get_name)
            )
        return root.variant_name

    @staticmethod
    def resolve_product_name(root: Union[CheckoutLine, OrderLine], info: ResolveInfo):
        if isinstance(root, CheckoutLine):

            def get_name(product):
                return product.name

            if not root.variant_id:
                return ""
            return (
                ProductByVariantIdLoader(info.context)
                .load(root.variant_id)
                .then(get_name)
            )
        return root.product_name

    @staticmethod
    def resolve_product_sku(root: Union[CheckoutLine, OrderLine], info: ResolveInfo):
        if isinstance(root, CheckoutLine):
            if not root.variant_id:
                return None

            def get_sku(variant):
                return variant.sku

            return (
                ProductVariantByIdLoader(info.context)
                .load(root.variant_id)
                .then(get_sku)
            )
        return root.product_sku

    @staticmethod
    def resolve_source_line(root: Union[CheckoutLine, OrderLine], _info: ResolveInfo):
        return root

    @staticmethod
    def resolve_unit_price(root: Union[CheckoutLine, OrderLine], info: ResolveInfo):
        if isinstance(root, CheckoutLine):

            def with_checkout(checkout):
                lines = CheckoutLinesInfoByCheckoutTokenLoader(info.context).load(
                    checkout.token
                )

                def calculate_line_unit_price(lines):
                    for line_info in lines:
                        if line_info.line.pk == root.pk:
                            return base_calculations.calculate_base_line_unit_price(
                                line_info=line_info,
                            )
                    return None

                return lines.then(calculate_line_unit_price)

            return (
                CheckoutByTokenLoader(info.context)
                .load(root.checkout_id)
                .then(with_checkout)
            )
        return root.base_unit_price

    @staticmethod
    def resolve_total_price(root: Union[CheckoutLine, OrderLine], info: ResolveInfo):
        if isinstance(root, CheckoutLine):

            def with_checkout(checkout):
                lines = CheckoutLinesInfoByCheckoutTokenLoader(info.context).load(
                    checkout.token
                )

                def calculate_line_total_price(lines):
                    for line_info in lines:
                        if line_info.line.pk == root.pk:
                            return base_calculations.calculate_base_line_total_price(
                                line_info=line_info
                            )
                    return None

                return lines.then(calculate_line_total_price)

            return (
                CheckoutByTokenLoader(info.context)
                .load(root.checkout_id)
                .then(with_checkout)
            )
        return root.base_unit_price * root.quantity


class TaxableObject(BaseObjectType):
    source_object = graphene.Field(
        TaxSourceObject,
        required=True,
        description="The source object related to this tax object.",
    )
    prices_entered_with_tax = graphene.Boolean(
        required=True, description="Determines if prices contain entered tax.."
    )
    currency = graphene.String(required=True, description="The currency of the object.")
    shipping_price = graphene.Field(
        MoneyType,
        required=True,
        description=(
            "The price of shipping method, includes shipping voucher discount "
            "if applied."
        ),
    )
    address = graphene.Field(
        "saleor.graphql.account.types.Address",
        description="The address data.",
    )
    lines = NonNullList(
        TaxableObjectLine,
        description="List of lines assigned to the object.",
        required=True,
    )
    channel = graphene.Field(Channel, required=True)

    class Meta:
        description = "Taxable object."
        doc_category = DOC_CATEGORY_TAXES

    @staticmethod
    def resolve_channel(root: Union[Checkout, Order], info: ResolveInfo):
        return ChannelByIdLoader(info.context).load(root.channel_id)

    @staticmethod
    def resolve_address(root: Union[Checkout, Order], info: ResolveInfo):
        address_id = root.shipping_address_id or root.billing_address_id
        if not address_id:
            return None
        return AddressByIdLoader(info.context).load(address_id)

    @staticmethod
    def resolve_source_object(root: Union[Checkout, Order], _info: ResolveInfo):
        return root

    @staticmethod
    def resolve_currency(root: Union[Checkout, Order], _info: ResolveInfo):
        return root.currency

    @staticmethod
    def resolve_shipping_price(root: Union[Checkout, Order], info: ResolveInfo):
        if isinstance(root, Checkout):

            def calculate_shipping_price(data):
                checkout_info, lines = data
                price = base_calculations.base_checkout_delivery_price(
                    checkout_info, lines
                )

                return quantize_price(
                    price,
                    checkout_info.checkout.currency,
                )

            checkout_info = CheckoutInfoByCheckoutTokenLoader(info.context).load(
                root.token
            )
            lines = CheckoutLinesInfoByCheckoutTokenLoader(info.context).load(
                root.token
            )
            return Promise.all(
                [
                    checkout_info,
                    lines,
                ]
            ).then(calculate_shipping_price)

        return root.base_shipping_price

    @staticmethod
    def resolve_discounts(root: Union[Checkout, Order], info: ResolveInfo):
        if isinstance(root, Checkout):

            def calculate_checkout_discounts(checkout_info):
                checkout = checkout_info.checkout
                discount_name = checkout.discount_name
                # All order level discounts applicable for checkout, like entire order
                # vouchers and order promotions, reduce subtotal value
                return (
                    [
                        {
                            "name": discount_name,
                            "amount": checkout.discount,
                            "type": "SUBTOTAL",
                        }
                    ]
                    if checkout.discount
                    and (
                        is_order_level_voucher(checkout_info.voucher)
                        or has_checkout_order_promotion(checkout_info)
                    )
                    else []
                )

            return (
                CheckoutInfoByCheckoutTokenLoader(info.context)
                .load(root.token)
                .then(calculate_checkout_discounts)
            )

        discounts = OrderDiscountsByOrderIDLoader(info.context).load(root.id)
        order_lines = OrderLinesByOrderIdLoader(info.context).load(root.id)

        def calculate_order_discounts(results):
            # Only order level discounts, like entire order vouchers,
            # order promotions and manual discounts should be taken into account.
            # Manual discount needs to be split into subtotal and shipping portions.
            (discounts, order_lines) = results
            taxable_discounts = []
            currency = root.currency
            for discount in discounts:
                shipping_discount = Money(0, currency)
                subtotal_discount = Money(0, currency)
                if discount.type == DiscountType.MANUAL:
                    subtotal = base_order_subtotal(root, order_lines)
                    shipping = root.base_shipping_price
                    subtotal_discount, shipping_discount = split_manual_discount(
                        discount, subtotal, shipping
                    )
                if (
                    is_order_level_voucher(discount.voucher)
                    or discount.type == DiscountType.ORDER_PROMOTION
                ):
                    subtotal_discount = discount.amount

                if subtotal_discount.amount:
                    taxable_discounts.append(
                        {
                            "name": discount.name,
                            "amount": subtotal_discount,
                            "type": "SUBTOTAL",
                        }
                    )
                if shipping_discount.amount:
                    taxable_discounts.append(
                        {
                            "name": discount.name,
                            "amount": shipping_discount,
                            "type": "SHIPPING",
                        }
                    )

            return taxable_discounts

        return Promise.all([discounts, order_lines]).then(calculate_order_discounts)

    @staticmethod
    def resolve_lines(root: Union[Checkout, Order], info: ResolveInfo):
        if isinstance(root, Checkout):
            return CheckoutLinesByCheckoutTokenLoader(info.context).load(root.token)
        return OrderLinesByOrderIdLoader(info.context).load(root.id)
