"""
Dashboard views for CSV Import History
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


@login_required
def csv_import_history(request):
    """
    View for displaying CSV import history page
    """
    if request.user.role not in ['TEACHER', 'ADMIN']:
        raise PermissionDenied
    
    return render(request, 'dashboard/teacher/import_history.html')
