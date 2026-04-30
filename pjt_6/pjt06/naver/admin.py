from django.contrib import admin

from .models import DiscussionPipelineResult


@admin.register(DiscussionPipelineResult)
class DiscussionPipelineResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "requirement_number",
        "requested_company_name",
        "actual_stock_name",
        "stock_code",
        "created_at",
    )
    search_fields = ("requested_company_name", "actual_stock_name", "stock_code")

# Register your models here.
