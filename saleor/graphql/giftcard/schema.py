import graphene
from graphql.error import GraphQLError

from ...giftcard import models
from ...giftcard.search import search_gift_cards
from ...permission.enums import GiftcardPermissions
from ..core import ResolveInfo
from ..core.connection import create_connection_slice, filter_connection_queryset
from ..core.context import get_database_connection_name
from ..core.descriptions import ADDED_IN_31, ADDED_IN_315, PREVIEW_FEATURE
from ..core.doc_category import DOC_CATEGORY_GIFT_CARDS
from ..core.fields import FilterConnectionField, PermissionsField
from ..core.types import NonNullList
from ..core.utils import from_global_id_or_error
from .filters import GiftCardFilterInput, GiftCardTagFilterInput
from .resolvers import resolve_gift_card, resolve_gift_cards
from .sorters import GiftCardSortingInput
from .types import GiftCard, GiftCardCountableConnection


class GiftCardQueries(graphene.ObjectType):
    gift_card = PermissionsField(
        GiftCard,
        id=graphene.Argument(
            graphene.ID, description="ID of the gift card.", required=True
        ),
        description="Look up a gift card by ID.",
        permissions=[
            GiftcardPermissions.MANAGE_GIFT_CARD,
        ],
        doc_category=DOC_CATEGORY_GIFT_CARDS,
    )
    gift_cards = FilterConnectionField(
        GiftCardCountableConnection,
        sort_by=GiftCardSortingInput(description="Sort gift cards." + ADDED_IN_31),
        filter=GiftCardFilterInput(
            description=("Filtering options for gift cards." + ADDED_IN_31)
        ),
        search=graphene.String(
            description="Search gift cards by email and name of user, "
            "who created or used the gift card, and by code."
            + ADDED_IN_315
            + PREVIEW_FEATURE
        ),
        description="List of gift cards.",
        permissions=[
            GiftcardPermissions.MANAGE_GIFT_CARD,
        ],
        doc_category=DOC_CATEGORY_GIFT_CARDS,
    )
    gift_card_currencies = PermissionsField(
        NonNullList(graphene.String),
        description="List of gift card currencies." + ADDED_IN_31,
        required=True,
        permissions=[
            GiftcardPermissions.MANAGE_GIFT_CARD,
        ],
        doc_category=DOC_CATEGORY_GIFT_CARDS,
    )

    @staticmethod
    def resolve_gift_card(_root, info: ResolveInfo, /, *, id: str):
        _, id = from_global_id_or_error(id, GiftCard)
        return resolve_gift_card(info, id)

    @staticmethod
    def resolve_gift_cards(
        _root, info: ResolveInfo, /, *, sort_by=None, filter=None, search=None, **kwargs
    ):
        sorting_by_balance = sort_by and "current_balance_amount" in sort_by.get(
            "field", []
        )
        filtering_by_currency = filter and "currency" in filter
        if sorting_by_balance and not filtering_by_currency:
            raise GraphQLError("Sorting by balance requires filtering by currency.")
        qs = resolve_gift_cards(info)
        if search:
            qs = search_gift_cards(qs, search)
        qs = filter_connection_queryset(
            qs,
            {"sort_by": sort_by, "filter": filter, **kwargs},
            allow_replica=info.context.allow_replica,
        )
        return create_connection_slice(
            qs,
            info,
            {"sort_by": sort_by, "filter": filter, **kwargs},
            GiftCardCountableConnection,
        )

    @staticmethod
    def resolve_gift_card_currencies(_root, info: ResolveInfo):
        return set(
            models.GiftCard.objects.using(
                get_database_connection_name(info.context)
            ).values_list("currency", flat=True)
        )
