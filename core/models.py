from django.db import models

class SiteSettings(models.Model):
    hero_title = models.CharField(max_length=200, blank=True, default="Welcome to our store")
    hero_text = models.TextField(blank=True, default="Best products at best prices.")
    hero_banner = models.ImageField(upload_to="banners/", null=True, blank=True)
    about_us = models.TextField(blank=True)

    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return "تنظیمات اصلی سایت"
