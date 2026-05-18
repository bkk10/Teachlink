"""
Teachly Main URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

schema_view = None
try:
    from rest_framework import permissions
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi

    # API documentation (optional in environments where drf_yasg deps are missing)
    schema_view = get_schema_view(
        openapi.Info(
            title="Teachly API",
            default_version="v1",
            description="Intelligent Student Risk Detection System",
            contact=openapi.Contact(email="support@teachly.com"),
            license=openapi.License(name="MIT License"),
        ),
        public=True,
        permission_classes=[permissions.AllowAny],
    )
except Exception:
    schema_view = None

urlpatterns = [
    # Landing Page - Home
    path('', TemplateView.as_view(template_name='landing.html'), name='home'),
    
    # Static Pages
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
    path('features/', TemplateView.as_view(template_name='features.html'), name='features'),
    path('privacy/', TemplateView.as_view(template_name='privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='terms.html'), name='terms'),
    path('contact/', TemplateView.as_view(template_name='contact.html'), name='contact'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/auth/', include('users.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/assessments/', include('assessments.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    
    # Dashboard HTML views
    path('dashboard/', include('dashboard.urls_html')),
]

if schema_view is not None:
    urlpatterns += [
        path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
        path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    ]

# Serve static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
