from urllib.parse import urlparse, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http.request import split_domain_port, validate_host

from . import build_absolute_uri


def prepare_url(params: str, redirect_url: str) -> str:
    """Add params to redirect url."""
    split_url = urlsplit(redirect_url)
    current_params = split_url.query
    if current_params:
        params = f"{current_params}&{params}"
    split_url = split_url._replace(query=params)
    return split_url.geturl()


def get_default_storage_root_url():
    """Return the absolute root URL for default storage."""
    # We cannot do simple `storage.url("")`, as the `AzureStorage` url method requires
    # at least one printable character that is not a slash or space.
    # Because of that, the `url` method is called for a `path` value, and then
    # `path` is stripped to get the actual root URL
    tmp_path = "path"
    return build_absolute_uri(default_storage.url(tmp_path)).rstrip(tmp_path)
