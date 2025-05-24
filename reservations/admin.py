from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Court, TimeSlot, Reservation, Vivienda, Usuario, ReservationInvitation, Community

# Configuración para el modelo Usuario
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'apellido', 'vivienda', 'is_staff', 'community')
    list_filter = ('vivienda', 'is_staff', 'community')
    search_fields = ('email', 'nombre', 'apellido')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('nombre', 'password')}),
        ('Información personal', {'fields': ('apellido', 'vivienda', 'email', 'community')}),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'apellido', 'vivienda', 'password1', 'password2', 'community'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')  # ← Campos de solo lectura
    
    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)

# Mantenemos tus configuraciones existentes
@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'direccion', 'community')
    search_fields = ('name', 'direccion', 'community__name')

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

@admin.register(ReservationInvitation)
class ReservationInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'reserva', 'invitado', 'email', 'estado', 'fecha_invitacion')
    search_fields = ('email', 'invitado__nombre', 'reserva__user__nombre')
    list_filter = ('estado', 'fecha_invitacion')

@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name',)