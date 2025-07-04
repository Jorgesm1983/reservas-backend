# Generated by Django 5.2 on 2025-06-15 12:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0008_vivienda_community"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="reservation",
            name="unique_reservation",
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                fields=("court", "timeslot", "date"),
                name="unique_reservation_per_court_timeslot_date",
            ),
        ),
    ]
