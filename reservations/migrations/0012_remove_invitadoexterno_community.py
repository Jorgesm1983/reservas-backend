# Generated by Django 5.2 on 2025-06-28 17:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0011_remove_invitadoexterno_community_community_code"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="invitadoexterno",
            name="community",
        ),
    ]
