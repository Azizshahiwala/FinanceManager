from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Finance', '0005_transactionlogs_source_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='username',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
