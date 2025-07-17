from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Court, TimeSlot, Reservation, Vivienda, Usuario, ReservationInvitation, Community, ReservationCancelada, InvitadoExterno
from django.urls import path
from django.template.response import TemplateResponse
from datetime import date, timedelta, datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseServerError
from .models import Community
from calendar import monthrange

# Configuración para el modelo Usuario
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'apellido', 'vivienda', 'is_staff', 'community', 'accepted_terms', 'terms_accepted_at')
    list_filter = ('vivienda', 'is_staff', 'community', 'accepted_terms')
    search_fields = ('email', 'nombre', 'apellido')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('nombre', 'password')}),
        ('Información personal', {'fields': ('apellido', 'vivienda', 'email', 'community')}),
        ('Consentimiento', {'fields': ('accepted_terms', 'terms_accepted_at')}),
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
    
    readonly_fields = ('date_joined', 'last_login', 'terms_accepted_at')  # ← Campos de solo lectura
    
    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)

# Mantenemos tus configuraciones existentes
@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('name', 'community', 'reserva_hora_apertura_pasado', 'reserva_max_dias')
    list_editable = ('reserva_hora_apertura_pasado', 'reserva_max_dias')
    list_filter = ('community',)
    
@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('slot', 'start_time', 'end_time', 'court')
    list_filter = ('court',)
    search_fields = ('court__name', 'slot')

    ordering = ('start_time',)

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'court', 'date', 'get_slot', 'created_at', 'estado')
    list_filter = ('date', 'court')
    raw_id_fields = ('user',)
    
    def get_slot(self, obj):
        return obj.timeslot.slot if obj.timeslot else "N/A"
    get_slot.short_description = 'Franja horaria'
    get_slot.admin_order_field = 'timeslot__slot'

# admin.site.register(Vivienda)
@admin.register(Vivienda)
class ViviendaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'community')
    list_filter = ('community',)
    search_fields = ('nombre',)


@admin.register(ReservationInvitation)
class ReservationInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'reserva', 'invitado', 'email','nombre_invitado', 'estado', 'fecha_invitacion')
    search_fields = ('email', 'invitado__nombre', 'reserva__user__nombre', 'nombre_invitado')
    list_filter = ('estado', 'fecha_invitacion')
    fields = (
        'reserva', 'invitado', 'email', 'nombre_invitado', 'estado', 'fecha_invitacion', 'token'
    )
    readonly_fields = ('fecha_invitacion', 'token')

@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'reserva_hora_apertura_pasado', 'reserva_max_dias')
    list_editable = ('reserva_hora_apertura_pasado', 'reserva_max_dias')
    

@admin.register(ReservationCancelada)
class ReservationCanceladaAdmin(admin.ModelAdmin):
    list_display = (
        'user', 
        'court', 
        'date', 
        'timeslot', 
        'created_at', 
        'cancelada_at'
    )
    list_filter = ('user', 'court', 'date', 'cancelada_at')
    search_fields = ('user__nombre', 'user__email', 'court__name')
    
@admin.register(InvitadoExterno)
class InvitadoExternoAdmin(admin.ModelAdmin):
    list_display = ('email', 'nombre', 'usuario', 'creado_en')
    search_fields = ('email', 'nombre', 'usuario__email')
    list_filter = ('usuario__community',)


from .statistics import (
    reservas_totales_periodo, reservas_por_pista, reservas_por_comunidad,
    porcentaje_ocupacion_por_pista, partidos_mes, partidos_semana, ranking_usuarios_activos,
    proporcion_usuarios_vs_staff, invitaciones_kpis, tasa_cancelaciones,
    reservas_por_horario, participacion_media, usuarios_nuevos,
    tiempo_medio_antelacion, cancelaciones_ultimo_minuto, participacion_por_vivienda
)

@staff_member_required
def estadisticas_dashboard_view(request):
    try:
        hoy = date.today()
        # Lectura y parseo de fechas desde el formulario
        from_date_str = request.GET.get('from_date')
        to_date_str = request.GET.get('to_date')

        if from_date_str:
            try:
                primer_dia_mes = datetime.strptime(from_date_str, "%Y-%m-%d").date()
            except ValueError:
                primer_dia_mes = hoy.replace(day=1)
        else:
            primer_dia_mes = hoy.replace(day=1)

        if to_date_str:
            try:
                ultimo_dia_mes = datetime.strptime(to_date_str, "%Y-%m-%d").date()
            except ValueError:
                ultimo_dia_mes = date(hoy.year, hoy.month, monthrange(hoy.year, hoy.month)[1])
        else:
            ultimo_dia_mes = date(hoy.year, hoy.month, monthrange(hoy.year, hoy.month)[1])

        # Semana "natural": lunes a domingo de la semana actual
        primer_dia_semana = hoy - timedelta(days=hoy.weekday())
        ultimo_dia_semana = primer_dia_semana + timedelta(days=6)

        comunidades_lista = Community.objects.all().order_by('name')
        community_id = request.GET.get("community_id") or None
        if community_id == "":
            community_id = None

        # --- KPIs ---
        ocupacion_pista = porcentaje_ocupacion_por_pista(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or []
        # Cálculo seguro de media de ocupación (para mostrar en el dashboard)
        ocupacion_media = None
        if ocupacion_pista:
            ocupaciones = [row['ocupacion_pct'] for row in ocupacion_pista if 'ocupacion_pct' in row]
            ocupacion_media = round(sum(ocupaciones) / len(ocupaciones), 1) if ocupaciones else 0

        context = dict(
            comunidades_lista=comunidades_lista,
            community_id=community_id,
            primer_dia_mes=primer_dia_mes,
            ultimo_dia_mes=ultimo_dia_mes,
            primer_dia_semana=primer_dia_semana,
            ultimo_dia_semana=ultimo_dia_semana,
            ocupacion_media=ocupacion_media,
            reservas_totales_mes=reservas_totales_periodo(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or 0,
            reservas_totales_semana=reservas_totales_periodo(primer_dia_semana, ultimo_dia_semana, community_id=community_id) or 0,
            reservas_pista=ocupacion_pista,
            reservas_comunidad=reservas_por_comunidad(primer_dia_mes, ultimo_dia_mes) or [],
            partidos_mes=partidos_mes(community_id=community_id) or 0,
            partidos_semana=partidos_semana(community_id=community_id) or 0,
            ranking_usuarios=ranking_usuarios_activos(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or [],
            proporcion_staff=proporcion_usuarios_vs_staff(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or {},
            invitaciones=invitaciones_kpis(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or {},
            cancelaciones=tasa_cancelaciones(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or {},
            por_horario=reservas_por_horario(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or [],
            participacion_media=participacion_media(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or 0,
            usuarios_nuevos=usuarios_nuevos(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or 0,
            antelacion=tiempo_medio_antelacion(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or 0,
            ult_minuto=cancelaciones_ultimo_minuto(primer_dia_mes, ultimo_dia_mes, community_id=community_id, horas=24) or {},
            por_vivienda=participacion_por_vivienda(primer_dia_mes, ultimo_dia_mes, community_id=community_id) or [],
        )
        return TemplateResponse(request, "admin/estadisticas_dashboard.html", context)
    except Exception as e:
        import traceback
        error_message = f"<h2>Error en Dashboard Estadístico</h2><pre>{traceback.format_exc()}</pre>"
        return HttpResponseServerError(error_message)