from typing import TypeVar

import graphene
from django.conf import settings
from django.db.models import Model

from ...attribute import AttributeInputType
from ...attribute import models as attribute_models
from ...attribute.models import AttributeValue
from ...menu import models as menu_models
from ...page import models as page_models
from ...site import models as site_models
from ..channel import ChannelContext
from ..core.context import get_database_connection_name
from ..core.descriptions import (
    ADDED_IN_39,
    ADDED_IN_314,
    DEPRECATED_IN_3X_FIELD,
    RICH_CONTENT,
)
from ..core.enums import LanguageCodeEnum
from ..core.fields import JSONString
from ..core.tracing import traced_resolver
from ..core.types import LanguageDisplay, ModelObjectType, NonNullList
from ..core.utils import str_to_enum
from ..menu.dataloaders import MenuItemByIdLoader
from .fields import TranslationField


def get_translatable_attribute_values(attributes: list) -> list[AttributeValue]:
    """Filter the list of passed attributes.

    Return those which are translatable attributes.
    """
    translatable_values: list[AttributeValue] = []
    for assignment in attributes:
        attr = assignment["attribute"]
        if attr.input_type in AttributeInputType.TRANSLATABLE_ATTRIBUTES:
            translatable_values.extend(assignment["values"])
    return translatable_values


T = TypeVar("T", bound=Model)


class BaseTranslationType(ModelObjectType[T]):
    language = graphene.Field(
        LanguageDisplay, description="Translation language.", required=True
    )

    class Meta:
        abstract = True

    @staticmethod
    @traced_resolver
    def resolve_language(root, _info):
        try:
            language = next(
                language[1]
                for language in settings.LANGUAGES
                if language[0] == root.language_code
            )
        except StopIteration:
            return None
        return LanguageDisplay(
            code=LanguageCodeEnum[str_to_enum(root.language_code)], language=language
        )


class AttributeValueTranslation(
    BaseTranslationType[attribute_models.AttributeValueTranslation]
):
    id = graphene.GlobalID(
        required=True, description="The ID of the attribute value translation."
    )
    name = graphene.String(
        required=True, description="Translated attribute value name."
    )
    rich_text = JSONString(
        description="Translated rich-text attribute value." + RICH_CONTENT
    )
    plain_text = graphene.String(description="Translated plain text attribute value .")
    translatable_content = graphene.Field(
        "saleor.graphql.translations.types.AttributeValueTranslatableContent",
        description="Represents the attribute value fields to translate."
        + ADDED_IN_314,
    )

    class Meta:
        model = attribute_models.AttributeValueTranslation
        interfaces = [graphene.relay.Node]
        description = "Represents attribute value translations."



class AttributeTranslation(BaseTranslationType[attribute_models.AttributeTranslation]):
    id = graphene.GlobalID(
        required=True, description="The ID of the attribute translation."
    )
    name = graphene.String(required=True, description="Translated attribute name.")
    translatable_content = graphene.Field(
        "saleor.graphql.translations.types.AttributeTranslatableContent",
        description="Represents the attribute fields to translate." + ADDED_IN_314,
    )

    class Meta:
        model = attribute_models.AttributeTranslation
        interfaces = [graphene.relay.Node]
        description = "Represents attribute translations."


class AttributeTranslatableContent(ModelObjectType[attribute_models.Attribute]):
    id = graphene.GlobalID(
        required=True, description="The ID of the attribute translatable content."
    )
    attribute_id = graphene.ID(
        required=True,
        description="The ID of the attribute to translate." + ADDED_IN_314,
    )
    name = graphene.String(
        required=True, description="Name of the attribute to translate."
    )
    translation = TranslationField(AttributeTranslation, type_name="attribute")


    @staticmethod
    def resolve_attribute(root: attribute_models.Attribute, _info):
        return root

    @staticmethod
    def resolve_attribute_id(root: attribute_models.Attribute, _info):
        return graphene.Node.to_global_id("Attribute", root.id)


class AttributeValueTranslatableContent(
    ModelObjectType[attribute_models.AttributeValue]
):
    id = graphene.GlobalID(
        required=True, description="The ID of the attribute value translatable content."
    )
    attribute_value_id = graphene.ID(
        required=True,
        description="The ID of the attribute value to translate." + ADDED_IN_314,
    )
    name = graphene.String(
        required=True,
        description="Name of the attribute value to translate.",
    )
    rich_text = JSONString(description="Attribute value." + RICH_CONTENT)
    plain_text = graphene.String(description="Attribute plain text value.")
    translation = TranslationField(
        AttributeValueTranslation, type_name="attribute value"
    )
    attribute = graphene.Field(
        AttributeTranslatableContent,
        description="Associated attribute that can be translated." + ADDED_IN_39,
    )

    class Meta:
        model = attribute_models.AttributeValue
        interfaces = [graphene.relay.Node]
        description = (
            "Represents attribute value's original translatable fields "
            "and related translations."
        )

    @staticmethod
    def resolve_attribute_value(root: attribute_models.AttributeValue, _info):
        return root

    @staticmethod
    def resolve_attribute_value_id(root: attribute_models.AttributeValue, _info):
        return graphene.Node.to_global_id("AttributeValue", root.id)


class PageTranslation(BaseTranslationType[page_models.PageTranslation]):
    id = graphene.GlobalID(required=True, description="The ID of the page translation.")
    seo_title = graphene.String(description="Translated SEO title.")
    seo_description = graphene.String(description="Translated SEO description.")
    title = graphene.String(description="Translated page title.")
    content = JSONString(description="Translated content of the page." + RICH_CONTENT)
    content_json = JSONString(
        description="Translated description of the page." + RICH_CONTENT,
        deprecation_reason=f"{DEPRECATED_IN_3X_FIELD} Use the `content` field instead.",
    )
    translatable_content = graphene.Field(
        "saleor.graphql.translations.types.PageTranslatableContent",
        description="Represents the page fields to translate." + ADDED_IN_314,
    )

    class Meta:
        model = page_models.PageTranslation
        interfaces = [graphene.relay.Node]
        description = "Represents page translations."

    @staticmethod
    def resolve_content_json(root: page_models.PageTranslation, _info):
        content = root.content
        return content if content is not None else {}


class PageTranslatableContent(ModelObjectType[page_models.Page]):
    id = graphene.GlobalID(
        required=True, description="The ID of the page translatable content."
    )
    page_id = graphene.ID(
        required=True, description="The ID of the page to translate." + ADDED_IN_314
    )
    seo_title = graphene.String(description="SEO title to translate.")
    seo_description = graphene.String(description="SEO description to translate.")
    title = graphene.String(required=True, description="Page title to translate.")
    content = JSONString(description="Content of the page to translate." + RICH_CONTENT)
    content_json = JSONString(
        description="Content of the page." + RICH_CONTENT,
        deprecation_reason=f"{DEPRECATED_IN_3X_FIELD} Use the `content` field instead.",
    )
    translation = TranslationField(PageTranslation, type_name="page")
    attribute_values = NonNullList(
        AttributeValueTranslatableContent,
        required=True,
        description="List of page content attribute values that can be translated.",
    )

    class Meta:
        model = page_models.Page
        interfaces = [graphene.relay.Node]
        description = (
            "Represents page's original translatable fields and related translations."
        )

    @staticmethod
    def resolve_page(root: page_models.Page, info):
        return (
            page_models.Page.objects.using(get_database_connection_name(info.context))
            .visible_to_user(info.context.user)
            .filter(pk=root.id)
            .first()
        )

    @staticmethod
    def resolve_content_json(root: page_models.Page, _info):
        content = root.content
        return content if content is not None else {}

    @staticmethod
    def resolve_page_id(root: page_models.Page, _info):
        return graphene.Node.to_global_id("Page", root.id)

class ShopTranslation(BaseTranslationType[site_models.SiteSettingsTranslation]):
    id = graphene.GlobalID(required=True, description="The ID of the shop translation.")
    header_text = graphene.String(
        required=True, description="Translated header text of sale."
    )
    description = graphene.String(
        required=True, description="Translated description of sale."
    )

    class Meta:
        model = site_models.SiteSettingsTranslation
        interfaces = [graphene.relay.Node]
        description = "Represents shop translations."


class MenuItemTranslation(BaseTranslationType[menu_models.MenuItemTranslation]):
    id = graphene.GlobalID(
        required=True, description="The ID of the menu item translation."
    )
    name = graphene.String(required=True, description="Translated menu item name.")
    translatable_content = graphene.Field(
        "saleor.graphql.translations.types.MenuItemTranslatableContent",
        description="Represents the menu item fields to translate." + ADDED_IN_314,
    )

    class Meta:
        model = menu_models.MenuItemTranslation
        interfaces = [graphene.relay.Node]
        description = "Represents menu item translations."

    @staticmethod
    def resolve_translatable_content(root: menu_models.MenuItemTranslation, info):
        return MenuItemByIdLoader(info.context).load(root.menu_item_id)


class MenuItemTranslatableContent(ModelObjectType[menu_models.MenuItem]):
    id = graphene.GlobalID(
        required=True, description="The ID of the menu item translatable content."
    )
    menu_item_id = graphene.ID(
        required=True,
        description="The ID of the menu item to translate." + ADDED_IN_314,
    )
    name = graphene.String(
        required=True, description="Name of the menu item to translate."
    )
    translation = TranslationField(MenuItemTranslation, type_name="menu item")
    menu_item = graphene.Field(
        "saleor.graphql.menu.types.MenuItem",
        description=(
            "Represents a single item of the related menu. Can store categories, "
            "collection or pages."
        ),
        deprecation_reason=(
            f"{DEPRECATED_IN_3X_FIELD} Get model fields from the root level queries."
        ),
    )

    class Meta:
        model = menu_models.MenuItem
        interfaces = [graphene.relay.Node]
        description = (
            "Represents menu item's original translatable fields "
            "and related translations."
        )

    @staticmethod
    def resolve_menu_item(root: menu_models.MenuItem, _info):
        return ChannelContext(node=root, channel_slug=None)

    @staticmethod
    def resolve_menu_item_id(root: menu_models.MenuItem, _info):
        return graphene.Node.to_global_id("MenuItem", root.id)
