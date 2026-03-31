"""
Custom permissions for TeachLink.
"""
from rest_framework import permissions


class IsTeacher(permissions.BasePermission):
    """Allow access only to teachers."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "TEACHER")


class IsStudent(permissions.BasePermission):
    """Allow access only to students."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "STUDENT")


class IsTeacherOrReadOnly(permissions.BasePermission):
    """
    Allow teachers to create/update/delete.
    Allow read-only for authenticated users.
    """

    def has_permission(self, request, view):
        user = request.user

        if request.method == "OPTIONS":
            return True

        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return getattr(user, "role", None) == "TEACHER"
