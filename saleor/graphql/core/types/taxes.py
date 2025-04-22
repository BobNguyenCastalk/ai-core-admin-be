from typing import Union

import graphene

from ...channel.types import Channel
from ...core.doc_category import DOC_CATEGORY_TAXES
from ...core.types import BaseObjectType
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
