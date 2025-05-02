from django.contrib import admin
from .models import Court, TimeSlot, Reservation

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'start_time', 'end_time')

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'court', 'date', 'slot')
    list_filter = ('court', 'date')