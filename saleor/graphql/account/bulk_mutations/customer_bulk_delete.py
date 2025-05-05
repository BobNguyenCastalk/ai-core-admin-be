import graphene

from ...core.mutations import ModelBulkDeleteMutation
from ...core.types import NonNullList


class UserBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = NonNullList(
            graphene.ID, required=True, description="List of user IDs to delete."
        )

    class Meta:
        abstract = True