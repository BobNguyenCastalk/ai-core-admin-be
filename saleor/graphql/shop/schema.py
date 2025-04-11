import graphene

from ...channel import models as channel_models
from ...permission.enums import OrderPermissions
from ..channel.types import OrderSettings
from ..core.context import get_database_connection_name
from ..core.descriptions import DEPRECATED_IN_3X_FIELD, DEPRECATED_IN_3X_MUTATION
from ..core.doc_category import DOC_CATEGORY_ORDERS
from ..core.fields import PermissionsField
from ..site.dataloaders import load_site_callback
from ..translations.mutations import ShopSettingsTranslate
from .types import Shop


class ShopQueries(graphene.ObjectType):
    shop = graphene.Field(
        Shop,
        description="Return information about the shop.",
        required=True,
    )
    order_settings = PermissionsField(
        OrderSettings,
        description=(
            "Order related settings from site settings. "
            "Returns `orderSettings` for the first `channel` in "
            "alphabetical order."
        ),
        deprecation_reason=(
            f"{DEPRECATED_IN_3X_FIELD} "
            "Use the `channel` query to fetch the `orderSettings` field instead."
        ),
        permissions=[OrderPermissions.MANAGE_ORDERS],
        doc_category=DOC_CATEGORY_ORDERS,
    )

    def resolve_shop(self, _info):
        return Shop()

    def resolve_order_settings(self, info):
        channel = (
            channel_models.Channel.objects.using(
                get_database_connection_name(info.context)
            )
            .filter(is_active=True)
            .order_by("slug")
            .first()
        )
        if channel is None:
            return None
        return OrderSettings(
            automatically_confirm_all_new_orders=(
                channel.automatically_confirm_all_new_orders
            ),
            automatically_fulfill_non_shippable_gift_card=(
                channel.automatically_fulfill_non_shippable_gift_card
            ),
        )

    @load_site_callback
    def resolve_gift_card_settings(self, _info, site):
        return site.settings


class ShopMutations(graphene.ObjectType):
    shop_settings_translate = ShopSettingsTranslate.Field()

