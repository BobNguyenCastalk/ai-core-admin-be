import graphene
from graphene import relay

from ...menu import models
from ...permission.utils import has_one_of_permissions
from ...product.models import ALL_PRODUCTS_PERMISSIONS
from ..channel.dataloaders import ChannelBySlugLoader
from ..channel.types import (
    ChannelContext,
    ChannelContextType,
    ChannelContextTypeWithMetadata,
)
from ..core import ResolveInfo
from ..core.connection import CountableConnection
from ..core.doc_category import DOC_CATEGORY_MENU
from ..core.types import NonNullList
from ..meta.types import ObjectWithMetadata
from ..translations.fields import TranslationField
from ..translations.types import MenuItemTranslation
from ..utils import get_user_or_app_from_context
from .dataloaders import (
    MenuByIdLoader,
    MenuItemByIdLoader,
    MenuItemChildrenLoader,
    MenuItemsByParentMenuLoader,
)


class Menu(ChannelContextTypeWithMetadata[models.Menu]):
    id = graphene.GlobalID(required=True, description="The ID of the menu.")
    name = graphene.String(required=True, description="The name of the menu.")
    slug = graphene.String(required=True, description="Slug of the menu.")
    items = NonNullList(
        lambda: MenuItem, description="Menu items associated with this menu."
    )

    class Meta:
        default_resolver = ChannelContextType.resolver_with_context
        description = (
            "Represents a single menu - an object that is used to help navigate "
            "through the store."
        )
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Menu

    @staticmethod
    def resolve_items(root: ChannelContext[models.Menu], info: ResolveInfo):
        menu_items = MenuItemsByParentMenuLoader(info.context).load(root.node.id)
        return menu_items.then(
            lambda menu_items: [
                ChannelContext(node=menu_item, channel_slug=root.channel_slug)
                for menu_item in menu_items
            ]
        )


class MenuCountableConnection(CountableConnection):
    class Meta:
        doc_category = DOC_CATEGORY_MENU
        node = Menu


class MenuItem(ChannelContextTypeWithMetadata[models.MenuItem]):
    id = graphene.GlobalID(required=True, description="The ID of the menu item.")
    name = graphene.String(required=True, description="The name of the menu item.")
    menu = graphene.Field(
        Menu,
        required=True,
        description="Represents the menu to which the menu item belongs.",
    )
    parent = graphene.Field(
        lambda: MenuItem,
        description="ID of parent menu item. If empty, menu will be top level menu.",
    )
    level = graphene.Int(
        required=True,
        description="Indicates the position of the menu item within the menu "
        "structure.",
    )
    children = NonNullList(
        lambda: MenuItem,
        description="Represents the child items of the current menu item.",
    )
    url = graphene.String(description="URL to the menu item.")
    translation = TranslationField(
        MenuItemTranslation,
        type_name="menu item",
        resolver=ChannelContextType.resolve_translation,
    )

    class Meta:
        default_resolver = ChannelContextType.resolver_with_context
        description = (
            "Represents a single item of the related menu. Can store categories, "
            "collection or pages."
        )
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.MenuItem

    @staticmethod
    def resolve_children(root: ChannelContext[models.MenuItem], info: ResolveInfo):
        menus = MenuItemChildrenLoader(info.context).load(root.node.id)
        return menus.then(
            lambda menus: [
                ChannelContext(node=menu, channel_slug=root.channel_slug)
                for menu in menus
            ]
        )

    @staticmethod
    def resolve_menu(root: ChannelContext[models.MenuItem], info: ResolveInfo):
        if root.node.menu_id:
            menu = MenuByIdLoader(info.context).load(root.node.menu_id)
            return menu.then(
                lambda menu: ChannelContext(node=menu, channel_slug=root.channel_slug)
            )
        return None

    @staticmethod
    def resolve_parent(root: ChannelContext[models.MenuItem], info: ResolveInfo):
        if root.node.parent_id:
            menu = MenuItemByIdLoader(info.context).load(root.node.parent_id)
            return menu.then(
                lambda menu: ChannelContext(node=menu, channel_slug=root.channel_slug)
            )
        return None

    @staticmethod
    def resolve_page(root: ChannelContext[models.MenuItem], info: ResolveInfo):
        return None


class MenuItemCountableConnection(CountableConnection):
    class Meta:
        node = MenuItem
        doc_category = DOC_CATEGORY_MENU


class MenuItemMoveInput(graphene.InputObjectType):
    item_id = graphene.ID(description="The menu item ID to move.", required=True)
    parent_id = graphene.ID(
        description="ID of the parent menu. If empty, menu will be top level menu."
    )
    sort_order = graphene.Int(
        description=(
            "The new relative sorting position of the item (from -inf to +inf). "
            "1 moves the item one position forward, -1 moves the item one position "
            "backward, 0 leaves the item unchanged."
        )
    )
