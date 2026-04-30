from django.db import models


class DiscussionPipelineResult(models.Model):
    requirement_number = models.CharField(max_length=20, default="F102")
    requested_company_name = models.CharField(max_length=100)
    actual_stock_name = models.CharField(max_length=100)
    stock_code = models.CharField(max_length=6, blank=True)
    original_comments = models.JSONField(default=list)
    cleaned_comments = models.JSONField(default=list)
    augmented_comments = models.JSONField(default=list)
    integrated_data = models.JSONField(default=list)
    iqr_thresholds = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requirement_number} {self.actual_stock_name} {self.created_at:%Y-%m-%d %H:%M:%S}"
