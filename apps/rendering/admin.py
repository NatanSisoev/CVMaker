from django.contrib import admin

from .models import Render


@admin.register(Render)
class RenderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cv",
        "language",
        "style",
        "status",
        "requested_at",
        "completed_at",
    )
    list_filter = ("status", "language", "style")
    search_fields = ("payload_hash", "cv__alias", "requested_by__email")
    readonly_fields = ("payload_hash", "requested_at", "completed_at")
    ordering = ("-requested_at",)
