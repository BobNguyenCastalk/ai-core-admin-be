from typing import Union

import graphene

from ....order.models import Order
from ...account.dataloaders import AddressByIdLoader
from ...channel.dataloaders import ChannelByIdLoader
from ...channel.types import Channel
from ...core.doc_category import DOC_CATEGORY_TAXES
from ...core.types import BaseObjectType
from .. import ResolveInfo
from .money import Money as MoneyType


class TaxableObject(BaseObjectType):
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
    channel = graphene.Field(Channel, required=True)

    class Meta:
        description = "Taxable object."
        doc_category = DOC_CATEGORY_TAXES

    @staticmethod
    def resolve_channel(root: Union[ Order], info: ResolveInfo):
        return ChannelByIdLoader(info.context).load(root.channel_id)

    @staticmethod
    def resolve_address(root: Union[Order], info: ResolveInfo):
        address_id = root.shipping_address_id or root.billing_address_id
        if not address_id:
            return None
        return AddressByIdLoader(info.context).load(address_id)

    @staticmethod
    def resolve_source_object(root: Union[Order], _info: ResolveInfo):
        return root

    @staticmethod
    def resolve_currency(root: Union[Order], _info: ResolveInfo):
        return root.currency
