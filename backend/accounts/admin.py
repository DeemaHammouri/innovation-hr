from django.contrib import admin

from .models import ActionLog, Capability, Department, Role, User

admin.site.register(Department)
admin.site.register(Capability, list_display=("code", "description"))
admin.site.register(Role, list_display=("key", "department", "is_head"), filter_horizontal=("capabilities",))
admin.site.register(User, list_display=("email", "full_name", "department", "role_ref", "is_active"))
admin.site.register(ActionLog, list_display=("user", "action", "timestamp", "ip_address"))
