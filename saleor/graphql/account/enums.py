from ...account import CustomerEvents
from ...graphql.core.enums import to_enum
from ..core.doc_category import DOC_CATEGORY_USERS
from ..core.types import BaseEnum
from ..core.utils import str_to_enum

# AddressTypeEnum = to_enum(AddressType, type_name="AddressTypeEnum")
AddressTypeEnum = to_enum(CustomerEvents, type_name="AddressTypeEnum")

CustomerEventsEnum = to_enum(CustomerEvents)
CustomerEventsEnum.doc_category = DOC_CATEGORY_USERS


class StaffMemberStatus(BaseEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"

    class Meta:
        description = "Represents status of a staff account."
        doc_category = DOC_CATEGORY_USERS

    @property
    def description(self):
        if self == StaffMemberStatus.ACTIVE:
            return "User account has been activated."
        elif self == StaffMemberStatus.DEACTIVATED:
            return "User account has not been activated yet."
        return None
