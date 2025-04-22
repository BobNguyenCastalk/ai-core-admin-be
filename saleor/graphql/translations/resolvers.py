from ...page import models as page_models
from ..core import ResolveInfo
from . import dataloaders

TYPE_TO_TRANSLATION_LOADER_MAP = {
    page_models.Page: dataloaders.PageTranslationByIdAndLanguageCodeLoader,
}


def resolve_translation(instance, info: ResolveInfo, *, language_code):
    """Get translation object from instance based on language code."""

    loader = TYPE_TO_TRANSLATION_LOADER_MAP.get(type(instance))
    if loader:
        return loader(info.context).load((instance.id, language_code))
    raise TypeError(f"No dataloader found to {type(instance)}")
