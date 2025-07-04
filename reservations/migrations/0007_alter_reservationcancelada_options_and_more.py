# Generated by Django 5.2 on 2025-06-14 21:33

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0006_reservationcancelada"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="reservationcancelada",
            options={"verbose_name_plural": "Reservas Canceladas"},
        ),
        migrations.AlterModelOptions(
            name="reservationinvitation",
            options={
                "ordering": ["-fecha_invitacion", "-id"],
                "verbose_name_plural": "Invitaciones",
            },
        ),
        migrations.AlterUniqueTogether(
            name="timeslot",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="community",
            name="direccion",
            field=models.CharField(
                blank=True, max_length=255, null=True, verbose_name="Dirección"
            ),
        ),
        migrations.AddField(
            model_name="timeslot",
            name="community",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="timeslots",
                to="reservations.community",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="timeslot",
            unique_together={("community", "start_time", "end_time")},
        ),
    ]
