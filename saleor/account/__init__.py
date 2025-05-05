class CustomerEvents:
    """The different customer event types."""

    # Account related events
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_ACTIVATED = "account_activated"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    PASSWORD_RESET_LINK_SENT = "password_reset_link_sent"
    PASSWORD_RESET = "password_reset"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_CHANGE_REQUEST = "email_changed_request"
    EMAIL_CHANGED = "email_changed"

    # Order related events
    DIGITAL_LINK_DOWNLOADED = "digital_link_downloaded"  # downloaded a digital good

    # Staff actions over customers events
    CUSTOMER_DELETED = "customer_deleted"  # staff user deleted a customer
    EMAIL_ASSIGNED = "email_assigned"  # the staff user assigned a email to the customer
    NAME_ASSIGNED = "name_assigned"  # the staff user added set a name to the customer
    NOTE_ADDED = "note_added"  # the staff user added a note to the customer

    CHOICES = [
        (ACCOUNT_CREATED, "The account was created"),
        (ACCOUNT_ACTIVATED, "The account was activated"),
        (ACCOUNT_DEACTIVATED, "The account was deactivated"),
        (PASSWORD_RESET_LINK_SENT, "Password reset link was sent to the customer"),
        (PASSWORD_RESET, "The account password was reset"),
        (
            EMAIL_CHANGE_REQUEST,
            "The user requested to change the account's email address.",
        ),
        (PASSWORD_CHANGED, "The account password was changed"),
        (EMAIL_CHANGED, "The account email address was changed"),
        (DIGITAL_LINK_DOWNLOADED, "A digital good was downloaded"),
        (CUSTOMER_DELETED, "A customer was deleted"),
        (NAME_ASSIGNED, "A customer's name was edited"),
        (EMAIL_ASSIGNED, "A customer's email address was edited"),
        (NOTE_ADDED, "A note was added to the customer"),
    ]
