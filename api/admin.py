from django.contrib import admin

from .models import Booking, Flight, Hotel, RecentSearch, TravelArtifact, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    ordering = ('email',)
    list_display = ('email', 'full_name', 'phone_number', 'is_staff', 'is_active')
    search_fields = ('email', 'full_name')
    list_filter = ('is_staff', 'is_active')
    fields = (
        'email',
        'username',
        'full_name',
        'phone_number',
        'is_active',
        'is_staff',
        'is_superuser',
        'groups',
        'user_permissions',
        'last_login',
        'date_joined',
    )
    readonly_fields = ('last_login', 'date_joined')

    def save_model(self, request, obj, form, change):
        if not obj.username:
            obj.username = obj.email
        super().save_model(request, obj, form, change)


admin.site.register(TravelArtifact)
admin.site.register(RecentSearch)
admin.site.register(Booking)
admin.site.register(Flight)
admin.site.register(Hotel)
