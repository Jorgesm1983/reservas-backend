# Generated by Django 5.2 on 2025-06-22 10:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0009_remove_reservation_unique_reservation_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="reservation",
            name="unique_reservation_per_court_timeslot_date",
        ),
        migrations.AddField(
            model_name="invitadoexterno",
            name="community",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="invitados_externos",
                to="reservations.community",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                fields=("court", "date", "timeslot"),
                name="unique_reservation_per_court_timeslot_date",
            ),
        ),
    ]
