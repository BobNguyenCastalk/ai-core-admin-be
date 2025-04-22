from ...account import events as account_events
from ...celeryconf import app
from ...graphql.core.utils import from_global_id_or_none
from ..email_common import EmailConfig, send_email


@app.task(compression="zlib")
def send_account_confirmation_email_task(
    recipient_email, payload, config, subject, template
):
    email_config = EmailConfig(**config)

    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=template,
    )


@app.task(compression="zlib")
def send_password_reset_email_task(recipient_email, payload, config, subject, template):
    user_id = payload.get("user", {}).get("id")
    email_config = EmailConfig(**config)

    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=template,
    )
    account_events.customer_password_reset_link_sent_event(
        user_id=from_global_id_or_none(user_id)
    )


@app.task(compression="zlib")
def send_request_email_change_email_task(
    recipient_email, payload, config, subject, template
):
    user_id = payload.get("user", {}).get("id")
    email_config = EmailConfig(**config)

    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=template,
    )
    account_events.customer_email_change_request_event(
        user_id=from_global_id_or_none(user_id),
        parameters={
            "old_email": payload.get("old_email"),
            "new_email": recipient_email,
        },
    )


@app.task(compression="zlib")
def send_user_change_email_notification_task(
    recipient_email, payload, config, subject, template
):
    user_id = payload.get("user", {}).get("id")
    email_config = EmailConfig(**config)

    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=template,
    )
    event_parameters = {
        "old_email": payload.get("old_email"),
        "new_email": payload.get("new_email"),
    }

    account_events.customer_email_changed_event(
        user_id=from_global_id_or_none(user_id), parameters=event_parameters
    )


@app.task(compression="zlib")
def send_account_delete_confirmation_email_task(
    recipient_email, payload, config, subject, template
):
    email_config = EmailConfig(**config)

    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=template,
    )


@app.task(compression="zlib")
def send_set_user_password_email_task(
    recipient_email, payload, config, subject, template
):
    email_config = EmailConfig(**config)

    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=template,
    )