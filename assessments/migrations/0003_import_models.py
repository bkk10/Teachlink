# Generated manually for CSV Import History Models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('assessments', '0002_question_competencies'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImportHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file_name', models.CharField(max_length=255)),
                ('original_file', models.FileField(upload_to='csv_imports/%Y/%m/%d/')),
                ('total_records', models.PositiveIntegerField(default=0)),
                ('success_count', models.PositiveIntegerField(default=0)),
                ('error_count', models.PositiveIntegerField(default=0)),
                ('warning_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('PARTIAL', 'Partial Success'), ('ROLLED_BACK', 'Rolled Back')], default='PENDING', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('processing_time_seconds', models.PositiveIntegerField(blank=True, null=True)),
                ('error_log', models.JSONField(default=list)),
                ('is_rolled_back', models.BooleanField(default=False)),
                ('rolled_back_at', models.DateTimeField(blank=True, null=True)),
                ('students_affected', models.JSONField(default=list)),
                ('risk_recalculated', models.BooleanField(default=False)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='csv_imports', to='courses.course')),
                ('rolled_back_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rolled_back_imports', to=settings.AUTH_USER_MODEL)),
                ('teacher', models.ForeignKey(limit_choices_to={'role__in': ['TEACHER', 'ADMIN']}, on_delete=django.db.models.deletion.CASCADE, related_name='csv_imports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'csv_import_history',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='ImportRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('row_number', models.PositiveIntegerField()),
                ('raw_data', models.JSONField()),
                ('student_email', models.CharField(max_length=255)),
                ('assessment_name', models.CharField(max_length=255)),
                ('score', models.DecimalField(decimal_places=2, max_digits=5)),
                ('date', models.DateField()),
                ('status', models.CharField(choices=[('SUCCESS', 'Success'), ('ERROR', 'Error'), ('WARNING', 'Warning'), ('SKIPPED', 'Skipped')], default='SUCCESS', max_length=20)),
                ('message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_edited', models.BooleanField(default=False)),
                ('edited_at', models.DateTimeField(blank=True, null=True)),
                ('original_score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('attempt', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_record', to='assessments.quizattempt')),
                ('edited_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='edited_import_records', to=settings.AUTH_USER_MODEL)),
                ('import_history', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='assessments.importhistory')),
                ('quiz', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='imported_attempts', to='assessments.quiz')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='imported_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'csv_import_records',
                'ordering': ['row_number'],
            },
        ),
        migrations.AddIndex(
            model_name='importhistory',
            index=models.Index(fields=['teacher', '-started_at'], name='csv_import__teacher__46a831_idx'),
        ),
        migrations.AddIndex(
            model_name='importhistory',
            index=models.Index(fields=['course', '-started_at'], name='csv_import__course_i_9d8f4f_idx'),
        ),
        migrations.AddIndex(
            model_name='importhistory',
            index=models.Index(fields=['status'], name='csv_import__status_3f5785_idx'),
        ),
        migrations.AddIndex(
            model_name='importrecord',
            index=models.Index(fields=['import_history', 'status'], name='csv_import__import__3b18ab_idx'),
        ),
        migrations.AddIndex(
            model_name='importrecord',
            index=models.Index(fields=['student_email'], name='csv_import__student_2e4b8f_idx'),
        ),
        migrations.AddIndex(
            model_name='importrecord',
            index=models.Index(fields=['assessment_name'], name='csv_import__assessm_8f74c6_idx'),
        ),
    ]
