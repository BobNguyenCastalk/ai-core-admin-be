import graphene

from ...permission.enums import (
    AccountPermissions,
    CheckoutPermissions,
    PaymentPermissions,
)
from ..core import ResolveInfo
from ..core.connection import create_connection_slice, filter_connection_queryset
from ..core.descriptions import (
    ADDED_IN_31,
    ADDED_IN_34,
    DEPRECATED_IN_3X_FIELD,
    DEPRECATED_IN_3X_INPUT,
)
from ..core.doc_category import DOC_CATEGORY_CHECKOUT
from ..core.fields import BaseField, ConnectionField, FilterConnectionField
from ..core.scalars import UUID
from ..payment.mutations import CheckoutPaymentCreate
from .filters import CheckoutFilterInput
from .resolvers import resolve_checkout, resolve_checkout_lines, resolve_checkouts
from .sorters import CheckoutSortingInput
from .types import (
    Checkout,
    CheckoutCountableConnection,
    CheckoutLineCountableConnection,
)


class CheckoutQueries(graphene.ObjectType):
    checkout = BaseField(
        Checkout,
        description=(
            "Look up a checkout by id.\n\nRequires one of the following permissions "
            "to query a checkout, if a checkout is in inactive channel: "
            f"{CheckoutPermissions.MANAGE_CHECKOUTS.name}, "
            f"{AccountPermissions.IMPERSONATE_USER.name}, "
            f"{PaymentPermissions.HANDLE_PAYMENTS.name}. "
        ),
        id=graphene.Argument(
            graphene.ID, description="The checkout's ID." + ADDED_IN_34
        ),
        token=graphene.Argument(
            UUID,
            description=(
                f"The checkout's token.{DEPRECATED_IN_3X_INPUT} Use `id` instead."
            ),
        ),
        doc_category=DOC_CATEGORY_CHECKOUT,
    )
    # FIXME we could optimize the below field
    checkouts = FilterConnectionField(
        CheckoutCountableConnection,
        sort_by=CheckoutSortingInput(description="Sort checkouts." + ADDED_IN_31),
        filter=CheckoutFilterInput(
            description="Filtering options for checkouts." + ADDED_IN_31
        ),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        permissions=[
            CheckoutPermissions.MANAGE_CHECKOUTS,
            PaymentPermissions.HANDLE_PAYMENTS,
        ],
        description="List of checkouts.",
        doc_category=DOC_CATEGORY_CHECKOUT,
    )
    checkout_lines = ConnectionField(
        CheckoutLineCountableConnection,
        description="List of checkout lines.",
        permissions=[
            CheckoutPermissions.MANAGE_CHECKOUTS,
        ],
        doc_category=DOC_CATEGORY_CHECKOUT,
    )

    @staticmethod
    def resolve_checkout(_root, info: ResolveInfo, *, token=None, id=None):
        return resolve_checkout(info, token, id)

    @staticmethod
    def resolve_checkouts(_root, info: ResolveInfo, *, channel=None, **kwargs):
        qs = resolve_checkouts(info, channel)
        qs = filter_connection_queryset(
            qs, kwargs, allow_replica=info.context.allow_replica
        )
        return create_connection_slice(qs, info, kwargs, CheckoutCountableConnection)

    @staticmethod
    def resolve_checkout_lines(_root, info: ResolveInfo, **kwargs):
        qs = resolve_checkout_lines(info)
        return create_connection_slice(
            qs, info, kwargs, CheckoutLineCountableConnection
        )


class CheckoutMutations(graphene.ObjectType):
    checkout_payment_create = CheckoutPaymentCreate.Field()
