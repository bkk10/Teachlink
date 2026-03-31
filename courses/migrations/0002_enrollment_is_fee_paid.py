from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollment",
            name="is_fee_paid",
            field=models.BooleanField(default=False),
        ),
    ]

