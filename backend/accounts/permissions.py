from rest_framework.permissions import BasePermission


class PasswordChangeNotPending(BasePermission):
    code = "password_change_required"
    message = "Please set your new password first."

    def has_permission(self, request, view):
        user = request.user
        return not (user and user.is_authenticated and user.must_change_password)


def required_capabilities(view, request):
    """The capability codes the view demands for this request, or None when the view declared nothing (which means deny).

    A view declares `required_capabilities` as either
      * a list: the same codes for every action (an empty list means "any signed-in person", and must be written on purpose), or
      * a dict keyed by action name (viewsets) or lower-case HTTP method (plain views); "*" is the fallback key.
    A person needs ALL of the codes listed for the action.
    """
    compute = getattr(view, "get_required_capabilities", None)
    if compute is not None:
        return compute(request)
    declared = getattr(view, "required_capabilities", None)
    if declared is None:
        return None
    if isinstance(declared, (list, tuple)):
        return list(declared)
    key = getattr(view, "action", None) or request.method.lower()
    if key in declared:
        return list(declared[key])
    if "*" in declared:
        return list(declared["*"])
    return None


def denied_message(view, request):
    """`denied_message` on a view is a string, or a dict keyed like required_capabilities."""
    declared = getattr(view, "denied_message", None)
    if isinstance(declared, dict):
        key = getattr(view, "action", None) or request.method.lower()
        declared = declared.get(key, declared.get("*"))
    return declared or HasCapability.message


class HasCapability(BasePermission):
    """The one permission class. Fails closed: a view (or an action) with no declaration refuses everybody.

    `denied_message` on a view (a string, or a dict per action) overrides the generic refusal text.
    """

    message = "You don't have permission to do this."
    code = "permission_denied"

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        method = request.method.lower()
        if getattr(view, method, None) is None:
            return True  # the view has no handler for this method: DRF answers 405 and nothing is exposed
        needed = required_capabilities(view, request)
        if needed is None:
            return False
        if all(user.has_capability(code) for code in needed):
            return True
        self.message = denied_message(view, request)
        return False
