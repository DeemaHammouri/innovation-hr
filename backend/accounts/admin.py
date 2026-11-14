from django.contrib import admin

from .models import ActionLog, Department, User

admin.site.register(Department)
admin.site.register(User, list_display=("email", "full_name", "department", "role", "is_active"))
admin.site.register(ActionLog, list_display=("user", "action", "timestamp", "ip_address"))
