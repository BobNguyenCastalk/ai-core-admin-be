from django.db import models

from ...core.models import SortableModel
from .base import AssociatedAttributeManager


class AssignedProductAttributeValue(SortableModel):
    value = models.ForeignKey(
        "AttributeValue",
        on_delete=models.CASCADE,
        related_name="productvalueassignment",
    )

    class Meta:
        unique_together = (("value"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.product.attributevalues.all()


class AttributeProduct(SortableModel):
    attribute = models.ForeignKey(
        "Attribute", related_name="attributeproduct", on_delete=models.CASCADE
    )

    objects = AssociatedAttributeManager()

    class Meta:
        unique_together = (("attribute"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.product_type.attributeproduct.all()
