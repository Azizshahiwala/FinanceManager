from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Finance', '0004_profile_streaming_data_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionlogs',
            name='source_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='transactionlogs',
            index=models.Index(fields=['user', 'type', 'source_id'], name='Finance_tran_user_8dd6e3_idx'),
        ),
    ]
