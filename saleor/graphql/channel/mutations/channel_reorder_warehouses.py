import graphene

from ....core.tracing import traced_atomic_transaction
from ....permission.enums import ChannelPermissions
from ...core import ResolveInfo
from ...core.descriptions import ADDED_IN_37
from ...core.doc_category import DOC_CATEGORY_CHANNELS
from ...core.inputs import ReorderInput
from ...core.mutations import BaseMutation
from ...core.types import ChannelError, NonNullList
from ...core.utils.reordering import perform_reordering
from ..types import Channel


class ChannelReorderWarehouses(BaseMutation):
    channel = graphene.Field(
        Channel, description="Channel within the warehouses are reordered."
    )

    class Arguments:
        channel_id = graphene.ID(
            description="ID of a channel.",
            required=True,
        )
        moves = NonNullList(
            ReorderInput,
            required=True,
            description=(
                "The list of reordering operations for the given channel warehouses."
            ),
        )

    class Meta:
        description = "Reorder the warehouses of a channel." + ADDED_IN_37
        doc_category = DOC_CATEGORY_CHANNELS
        permissions = (ChannelPermissions.MANAGE_CHANNELS,)
        error_type_class = ChannelError

    @classmethod
    def perform_mutation(  # type: ignore[override]
        cls, _root, info: ResolveInfo, /, *, channel_id, moves
    ):
        channel = cls.get_node_or_error(
            info, channel_id, field="channel_id", only_type=Channel
        )
        return ChannelReorderWarehouses(channel=channel)