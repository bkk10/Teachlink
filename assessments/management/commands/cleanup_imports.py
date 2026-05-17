"""
Clean up old CSV imports to allow fresh re-import with proper quiz creation.
Run: python manage.py cleanup_imports
"""
from django.core.management.base import BaseCommand
from assessments.import_models import ImportHistory, ImportRecord
from assessments.models import QuizAttempt

class Command(BaseCommand):
    help = 'Clean up CSV imports and their quiz attempts'

    def handle(self, *args, **options):
        # Find imports of the ML assessment file
        imports = ImportHistory.objects.filter(file_name='students_ml_assessment.csv')
        
        self.stdout.write(f"Found {imports.count()} ML assessment imports to clean up")
        
        for imp in imports:
            self.stdout.write(f"\nProcessing import: {imp.id} ({imp.status})")
            
            # Get all records
            records = ImportRecord.objects.filter(import_history=imp)
            self.stdout.write(f"  - {records.count()} records")
            
            deleted_attempts = 0
            for record in records:
                if record.attempt:
                    record.attempt.delete()
                    deleted_attempts += 1
            
            # Delete records
            records.delete()
            
            # Mark as rolled back
            imp.is_rolled_back = True
            imp.status = ImportHistory.Status.ROLLED_BACK
            imp.save()
            
            self.stdout.write(f"  - Deleted {deleted_attempts} quiz attempts")
            self.stdout.write(self.style.SUCCESS(f"  - Cleaned up import {imp.id}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Cleanup complete! You can now re-import the CSV."))
