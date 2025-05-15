from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model



User = get_user_model()


class Court(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class TimeSlot(models.Model):
    """
    Franjas horarias predefinidas. Ej: 08:00–09:00, 09:00–10:00…
    """
    slot = models.CharField(max_length=50)  # Ejemplo: "10:00 - 11:00"
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('start_time', 'end_time')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    court = models.ForeignKey('Court', on_delete=models.CASCADE, related_name='court_reservations' ) # ← Cambiado para evitar conflicto)
    timeslot = models.ForeignKey('TimeSlot', on_delete=models.CASCADE, related_name='timeslot_reservations'
    )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('court', 'timeslot', 'date')  # Ahora válido
        verbose_name = 'Reservation'
        verbose_name_plural = 'Reservations'

    def __str__(self):
        return f"{self.user.username} - {self.court.name} - {self.date} {self.timeslot.start_time}-{self.timeslot.end_time}"

    def can_be_cancelled_by(self, user):
        return self.user == user or user.is_staff