import graphene

from ...attribute.models import Attribute, AttributeValue
from ...menu.models import MenuItem
from ...page.models import Page
from ...permission.enums import SitePermissions
from ...product.models import Category, Collection, Product, ProductVariant
from ..core import ResolveInfo
from ..core.connection import CountableConnection, create_connection_slice
from ..core.context import get_database_connection_name
from ..core.fields import ConnectionField, PermissionsField
from ..core.utils import from_global_id_or_error
from ..menu.resolvers import resolve_menu_items
from ..product.resolvers import resolve_categories
from ..translations import types as translation_types
from .resolvers import (
    resolve_collections,
    resolve_product_variants,
    resolve_products,
)

TYPES_TRANSLATIONS_MAP = {
    Product: translation_types.ProductTranslatableContent,
    Collection: translation_types.CollectionTranslatableContent,
    Category: translation_types.CategoryTranslatableContent,
    Attribute: translation_types.AttributeTranslatableContent,
    AttributeValue: translation_types.AttributeValueTranslatableContent,
    ProductVariant: translation_types.ProductVariantTranslatableContent,
    Page: translation_types.PageTranslatableContent,
    MenuItem: translation_types.MenuItemTranslatableContent,
}


class TranslatableItem(graphene.Union):
    class Meta:
        types = tuple(TYPES_TRANSLATIONS_MAP.values())

    @classmethod
    def resolve_type(cls, instance, info: ResolveInfo):
        instance_type = type(instance)
        if instance_type in TYPES_TRANSLATIONS_MAP:
            return TYPES_TRANSLATIONS_MAP[instance_type]

        return super().resolve_type(instance, info)


class TranslatableItemConnection(CountableConnection):
    class Meta:
        node = TranslatableItem


class TranslatableKinds(graphene.Enum):
    ATTRIBUTE = "Attribute"
    ATTRIBUTE_VALUE = "AttributeValue"
    CATEGORY = "Category"
    COLLECTION = "Collection"
    MENU_ITEM = "MenuItem"
    PAGE = "Page"
    PRODUCT = "Product"
    SALE = "Sale"
    VARIANT = "ProductVariant"


class TranslationQueries(graphene.ObjectType):
    translations = ConnectionField(
        TranslatableItemConnection,
        description="Returns a list of all translatable items of a given kind.",
        kind=graphene.Argument(
            TranslatableKinds, required=True, description="Kind of objects to retrieve."
        ),
        permissions=[
            SitePermissions.MANAGE_TRANSLATIONS,
        ],
    )
    translation = PermissionsField(
        TranslatableItem,
        description="Lookup a translatable item by ID.",
        id=graphene.Argument(
            graphene.ID, description="ID of the object to retrieve.", required=True
        ),
        kind=graphene.Argument(
            TranslatableKinds,
            required=True,
            description="Kind of the object to retrieve.",
        ),
        permissions=[SitePermissions.MANAGE_TRANSLATIONS],
    )

    @staticmethod
    def resolve_translations(_root, info: ResolveInfo, *, kind, **kwargs):
        if kind == TranslatableKinds.PRODUCT:
            qs = resolve_products(info)
        elif kind == TranslatableKinds.COLLECTION:
            qs = resolve_collections(info)
        elif kind == TranslatableKinds.CATEGORY:
            qs = resolve_categories(info)
        elif kind == TranslatableKinds.VARIANT:
            qs = resolve_product_variants(info)
        elif kind == TranslatableKinds.MENU_ITEM:
            qs = resolve_menu_items(info)

        return create_connection_slice(qs, info, kwargs, TranslatableItemConnection)

    @staticmethod
    def resolve_translation(_root, info: ResolveInfo, *, id, kind):
        _type, kind_id = from_global_id_or_error(id)
        if not _type == kind:
            return None
        models = {
            TranslatableKinds.PRODUCT.value: Product,  # type: ignore[attr-defined]
            TranslatableKinds.COLLECTION.value: Collection,  # type: ignore[attr-defined] # noqa: E501
            TranslatableKinds.CATEGORY.value: Category,  # type: ignore[attr-defined]
            TranslatableKinds.ATTRIBUTE.value: Attribute,  # type: ignore[attr-defined]
            TranslatableKinds.ATTRIBUTE_VALUE.value: AttributeValue,  # type: ignore[attr-defined] # noqa: E501
            TranslatableKinds.VARIANT.value: ProductVariant,  # type: ignore[attr-defined] # noqa: E501
            TranslatableKinds.PAGE.value: Page,  # type: ignore[attr-defined]
            TranslatableKinds.MENU_ITEM.value: MenuItem,  # type: ignore[attr-defined]
        }
        return (
            models[kind]
            .objects.using(get_database_connection_name(info.context))  # type: ignore[attr-defined]
            .filter(pk=kind_id)
            .first()
        )
