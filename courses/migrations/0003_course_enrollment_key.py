import uuid
from django.db import migrations, models
import courses.models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0002_enrollment_is_fee_paid"),
    ]

    def populate_enrollment_keys(apps, schema_editor):
        Course = apps.get_model("courses", "Course")
        used = set()
        seen_ids = set()

        # Keep valid unique existing keys, rewrite null/blank/duplicates.
        for course in Course.objects.exclude(enrollment_key__isnull=True).exclude(enrollment_key=""):
            key = (course.enrollment_key or "").strip().upper()
            if key and key not in used:
                if key != course.enrollment_key:
                    course.enrollment_key = key
                    course.save(update_fields=["enrollment_key"])
                used.add(key)
                seen_ids.add(course.id)
        for course in Course.objects.exclude(id__in=seen_ids):
            key = uuid.uuid4().hex[:8].upper()
            while key in used:
                key = uuid.uuid4().hex[:8].upper()
            course.enrollment_key = key
            course.save(update_fields=["enrollment_key"])
            used.add(key)

    operations = [
        migrations.AddField(
            model_name="course",
            name="enrollment_key",
            field=models.CharField(
                help_text="Key students can use to self-enroll",
                max_length=12,
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(populate_enrollment_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="course",
            name="enrollment_key",
            field=models.CharField(
                default=courses.models.default_course_key,
                help_text="Key students can use to self-enroll",
                max_length=12,
                unique=True,
            ),
        ),
    ]
