from collections.abc import Iterable
from enum import Enum
from typing import Optional

from graphql import GraphQLError


class PermissionDenied(Exception):
    def __init__(self, message=None, *, permissions: Optional[Iterable[Enum]] = None):
        if not message:
            if permissions:
                permission_list = ", ".join(p.name for p in permissions)
                message = (
                    "To access this path, you need one of the "
                    f"following permissions: {permission_list}"
                )
            else:
                message = "You do not have permission to perform this action"
        super().__init__(message)
        self.permissions = permissions


class CircularSubscriptionSyncEvent(GraphQLError):
    pass


class SyncEventError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message, code)
        self.message = message
        self.code = code

    def __str__(self):
        return self.message
