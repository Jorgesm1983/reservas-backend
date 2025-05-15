from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Court, TimeSlot, Reservation, Vivienda, Usuario

# Configuración para el modelo Usuario
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'apellido', 'vivienda', 'is_staff')
    list_filter = ('vivienda', 'is_staff')
    search_fields = ('email', 'nombre', 'apellido')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('nombre', 'password')}),
        ('Información personal', {'fields': ('apellido', 'vivienda', 'email')}),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'apellido', 'vivienda', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')  # ← Campos de solo lectura

# Mantenemos tus configuraciones existentes
@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'start_time', 'end_time', 'slot')
    list_editable = ('slot',)
    ordering = ('start_time',)

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'court', 'date', 'get_slot', 'created_at')
    list_filter = ('date', 'court')
    raw_id_fields = ('user',)
    
    def get_slot(self, obj):
        return obj.timeslot.slot if obj.timeslot else "N/A"
    get_slot.short_description = 'Franja horaria'
    get_slot.admin_order_field = 'timeslot__slot'

admin.site.register(Vivienda)
