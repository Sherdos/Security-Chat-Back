from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chats", "0004_groupencryptedkey"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="is_read",
            field=models.BooleanField(default=False),
        ),
    ]
