from ...attribute import models as attribute_models
from ...menu import models as menu_models
from ...page import models as page_models
from ...site import models as site_models
from ..core import ResolveInfo
from ..core.context import get_database_connection_name
from . import dataloaders

TYPE_TO_TRANSLATION_LOADER_MAP = {
    attribute_models.Attribute: (
        dataloaders.AttributeTranslationByIdAndLanguageCodeLoader
    ),
    attribute_models.AttributeValue: (
        dataloaders.AttributeValueTranslationByIdAndLanguageCodeLoader
    ),
    menu_models.MenuItem: (dataloaders.MenuItemTranslationByIdAndLanguageCodeLoader),
    page_models.Page: dataloaders.PageTranslationByIdAndLanguageCodeLoader,
    site_models.SiteSettings: (
        dataloaders.SiteSettingsTranslationByIdAndLanguageCodeLoader
    ),
}


def resolve_translation(instance, info: ResolveInfo, *, language_code):
    """Get translation object from instance based on language code."""

    loader = TYPE_TO_TRANSLATION_LOADER_MAP.get(type(instance))
    if loader:
        return loader(info.context).load((instance.id, language_code))
    raise TypeError(f"No dataloader found to {type(instance)}")


def resolve_attribute_values(info):
    return attribute_models.AttributeValue.objects.using(
        get_database_connection_name(info.context)
    ).all()


def resolve_products(info):
    return product_models.Product.objects.using(
        get_database_connection_name(info.context)
    ).all()


def resolve_product_variants(info):
    return product_models.ProductVariant.objects.using(
        get_database_connection_name(info.context)
    ).all()


def resolve_collections(info):
    return product_models.Collection.objects.using(
        get_database_connection_name(info.context)
    ).all()
