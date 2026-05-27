from django.contrib import admin

from .models import Activity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    """Activity rows are append-only for audit — no edits or deletes via admin."""

    list_display = ("action", "incident", "change", "problem", "user", "actor_ip", "created_at")
    list_filter = ("action",)
    search_fields = ("description", "old_value", "new_value")
    readonly_fields = [f.name for f in Activity._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
