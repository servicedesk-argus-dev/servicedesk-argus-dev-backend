from rest_framework import serializers
from django.utils.text import slugify
from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        if not attrs.get("slug") and attrs.get("name"):
            base = slugify(attrs["name"]) or "client"
            slug = base
            counter = 2
            while Organization.objects.filter(slug=slug).exclude(pk=getattr(self.instance, "pk", None)).exists():
                slug = f"{base}-{counter}"
                counter += 1
            attrs["slug"] = slug
        return attrs
