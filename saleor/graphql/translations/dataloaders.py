from collections import defaultdict

from ...attribute import models as attribute_models
from ...menu import models as menu_models
from ...page import models as page_models
from ...site import models as site_models
from ..core.dataloaders import DataLoader


class BaseTranslationByIdAndLanguageCodeLoader(DataLoader):
    model = None
    relation_name = None

    def batch_load(self, keys):
        if not self.model:
            raise ValueError("Provide a model for this dataloader.")
        if not self.relation_name:
            raise ValueError("Provide a relation_name for this dataloader.")

        ids = set([str(key[0]) for key in keys])
        language_codes = set([key[1] for key in keys])

        filters = {
            "language_code__in": language_codes,
            f"{self.relation_name}__in": ids,
        }

        translations = self.model.objects.using(self.database_connection_name).filter(
            **filters
        )
        translation_by_language_code_by_id = defaultdict(
            lambda: defaultdict(lambda: None)
        )
        for translation in translations:
            language_code = translation.language_code
            id = str(getattr(translation, self.relation_name))
            translation_by_language_code_by_id[language_code][id] = translation
        return [translation_by_language_code_by_id[key[1]][str(key[0])] for key in keys]


class AttributeTranslationByIdAndLanguageCodeLoader(
    BaseTranslationByIdAndLanguageCodeLoader
):
    context_key = "attribute_translation_by_id_and_language_code"
    model = attribute_models.AttributeTranslation
    relation_name = "attribute_id"


class AttributeValueTranslationByIdAndLanguageCodeLoader(
    BaseTranslationByIdAndLanguageCodeLoader
):
    context_key = "attribute_value_translation_by_id_and_language_code"
    model = attribute_models.AttributeValueTranslation
    relation_name = "attribute_value_id"


class MenuItemTranslationByIdAndLanguageCodeLoader(
    BaseTranslationByIdAndLanguageCodeLoader
):
    context_key = "menu_item_translation_by_id_and_language_code"
    model = menu_models.MenuItemTranslation
    relation_name = "menu_item_id"


class PageTranslationByIdAndLanguageCodeLoader(
    BaseTranslationByIdAndLanguageCodeLoader
):
    context_key = "page_translation_by_id_and_language_code"
    model = page_models.PageTranslation
    relation_name = "page_id"


class SiteSettingsTranslationByIdAndLanguageCodeLoader(
    BaseTranslationByIdAndLanguageCodeLoader
):
    context_key = "site_settings_translation_by_id_and_language_code"
    model = site_models.SiteSettingsTranslation
    relation_name = "site_settings_id"