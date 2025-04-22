from django.db import models

from ...core.models import SortableModel
from .base import AssociatedAttributeManager, AttributeValue, BaseAssignedAttribute


class AssignedVariantAttributeValue(SortableModel):
    value = models.ForeignKey(
        "AttributeValue",
        on_delete=models.CASCADE,
        related_name="variantvalueassignment",
    )
    assignment = models.ForeignKey(
        "AssignedVariantAttribute",
        on_delete=models.CASCADE,
        related_name="variantvalueassignment",
    )

    class Meta:
        unique_together = (("value", "assignment"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.assignment.variantvalueassignment.all()


class AssignedVariantAttribute(BaseAssignedAttribute):
    """Associate a product type attribute and selected values to a given variant."""

    assignment = models.ForeignKey(
        "AttributeVariant", on_delete=models.CASCADE, related_name="variantassignments"
    )
    values = models.ManyToManyField(
        AttributeValue,
        blank=True,
        related_name="variantassignments",
        through=AssignedVariantAttributeValue,
    )

    class Meta:
        unique_together = (("assignment"),)


class AttributeVariant(SortableModel):
    attribute = models.ForeignKey(
        "Attribute", related_name="attributevariant", on_delete=models.CASCADE
    )
    variant_selection = models.BooleanField(default=False)

    objects = AssociatedAttributeManager()

    class Meta:
        unique_together = (("attribute"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.product_type.attributevariant.all()
