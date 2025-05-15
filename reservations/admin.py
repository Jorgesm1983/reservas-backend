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
    list_display = ('id', 'user', 'court', 'date', 'get_slot', 'created_at')
    
    def get_slot(self, obj):
        if not obj.timeslot:
            return "⚠️ Sin franja horaria"
        return obj.timeslot.slot if obj.timeslot else "N/A"  # ← Maneja None
    get_slot.short_description = 'Franja horaria'  # Nombre de la columna
    get_slot.admin_order_field = 'timeslot__slot'  # Permite ordenar por este campo
