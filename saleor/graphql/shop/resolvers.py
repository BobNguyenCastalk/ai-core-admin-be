from django.utils import translation
from django_countries import countries

from ..core.context import get_database_connection_name
from ..core.types import CountryDisplay
from .utils import get_countries_codes_list

def resolve_countries(info, **kwargs):
    countries_filter = kwargs.get("filter", {})
    attached_to_shipping_zones = countries_filter.get("attached_to_shipping_zones")
    language_code = kwargs.get("language_code")
    database_connection_name = get_database_connection_name(info.context)
    codes_list = get_countries_codes_list(
        attached_to_shipping_zones, database_connection_name=database_connection_name
    )
    # DEPRECATED: translation.override will be dropped in Saleor 4.0
    with translation.override(language_code):
        return [
            CountryDisplay(code=country[0], country=country[1], vat=None)
            for country in countries
            if country[0] in codes_list
        ]


def get_shipping_method_to_listing_mapping(info, shipping_methods, channel_slug):
    """Prepare mapping shipping method to its channel listings."""
    shipping_mapping = {}
    shipping_listings = []
    for listing in shipping_listings:
        shipping_mapping[listing.shipping_method_id] = listing

    return shipping_mapping
