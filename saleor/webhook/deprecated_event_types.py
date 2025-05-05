class WebhookEventType:
    ANY = "any_events"
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_UPDATED = "customer_updated"

    DISPLAY_LABELS = {
        ANY: "Any events",
        CUSTOMER_CREATED: "Customer created",
        CUSTOMER_UPDATED: "Customer updated",
    }

    CHOICES = [
        (ANY, DISPLAY_LABELS[ANY]),
        (CUSTOMER_CREATED, DISPLAY_LABELS[CUSTOMER_CREATED]),
        (CUSTOMER_UPDATED, DISPLAY_LABELS[CUSTOMER_UPDATED]),
    ]
