from rest_framework.permissions import BasePermission


class PasswordChangeNotPending(BasePermission):
    code = "password_change_required"
    message = "Please set your new password first."

    def has_permission(self, request, view):
        user = request.user
        return not (user and user.is_authenticated and user.must_change_password)


class IsCEO(BasePermission):
    message = "Only the CEO can do this."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_ceo)


class CanManageClients(BasePermission):
    message = "Only the Operation Manager and the CEO can manage clients."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.can_manage_clients)
