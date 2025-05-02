from django.db import models
from django.contrib.auth.models import User

class Court(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class TimeSlot(models.Model):
    """
    Franjas horarias predefinidas. Ej: 08:00–09:00, 09:00–10:00…
    """
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('start_time', 'end_time')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    court = models.ForeignKey(Court, on_delete=models.CASCADE)
    date = models.DateField()
    slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, null=True)

    class Meta:
        unique_together = ('court', 'date', 'slot')
        ordering = ['date', 'slot']

    def __str__(self):
        return f"{self.date} {self.slot} @ {self.court}"