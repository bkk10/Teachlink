from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserSession

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'display_name', 'role', 'is_active', 'last_activity')
    list_filter = ('role', 'is_active', 'date_joined')
    search_fields = ('email', 'display_name', 'username')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info', {'fields': ('display_name', 'bio', 'avatar')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser',
                                   'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'last_activity', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'display_name', 'role', 
                      'password1', 'password2', 'is_active'),
        }),
    )

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'started_at', 'last_activity', 'ended_at')
    list_filter = ('started_at',)
    search_fields = ('user__email',)
    readonly_fields = ('id', 'session_key', 'duration_seconds')