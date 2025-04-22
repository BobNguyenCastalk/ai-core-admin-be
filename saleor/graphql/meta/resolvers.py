from operator import itemgetter

from ...account import models as account_models
from ...app import models as app_models
from ...channel import models as channel_models
from ...core.exceptions import PermissionDenied
from ...core.models import ModelWithMetadata
from ...permission.utils import one_of_permissions_or_auth_filter_required
from ..core import ResolveInfo
from ..utils import get_user_or_app_from_context
from .permissions import PRIVATE_META_PERMISSION_MAP


def resolve_object_with_metadata_type(instance):
    # Imports inside resolvers to avoid circular imports.
    from ...menu import models as menu_models
    from ..account import types as account_types
    from ..app import types as app_types
    from ..attribute import types as attribute_types
    from ..channel import types as channel_types
    from ..menu import types as menu_types

    if isinstance(instance, ModelWithMetadata):
        MODEL_TO_TYPE_MAP = {
            account_models.Address: account_types.Address,
            account_models.User: account_types.User,
            app_models.App: app_types.App,
            channel_models.Channel: channel_types.Channel,
            menu_models.Menu: menu_types.Menu,
            menu_models.MenuItem: menu_types.MenuItem,
        }
        return MODEL_TO_TYPE_MAP.get(instance.__class__, None), instance.pk

    raise ValueError(f"Unknown type: {instance.__class__}")


def resolve_metadata(metadata: dict):
    return sorted(
        [{"key": k, "value": v} for k, v in metadata.items()],
        key=itemgetter("key"),
    )


def check_private_metadata_privilege(root: ModelWithMetadata, info: ResolveInfo):
    item_type, item_id = resolve_object_with_metadata_type(root)
    if not item_type:
        raise NotImplementedError(
            f"Model {type(root)} can't be mapped to type with metadata. "
            "Make sure that model exists inside MODEL_TO_TYPE_MAP."
        )

    get_required_permission = PRIVATE_META_PERMISSION_MAP.get(item_type.__name__)
    if not get_required_permission:
        raise PermissionDenied()

    required_permissions = get_required_permission(info, item_id)

    if not isinstance(required_permissions, list):
        raise PermissionDenied()

    requester = get_user_or_app_from_context(info.context)
    if not requester or not one_of_permissions_or_auth_filter_required(
        info.context, required_permissions
    ):
        raise PermissionDenied()


def resolve_private_metadata(root: ModelWithMetadata, info: ResolveInfo):
    check_private_metadata_privilege(root, info)
    return resolve_metadata(root.private_metadata)
