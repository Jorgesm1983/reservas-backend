# reservations/statistics.py

from datetime import date, timedelta
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.db.models.functions import TruncWeek
from .models import Reservation, ReservationCancelada, ReservationInvitation, Court, Usuario, TimeSlot

# --- Utilidad filtro comunidad ---
def get_community_filter(community_id):
    if community_id:
        return {'court__community_id': community_id}
    return {}

# --- Reservas totales por periodo ---
def reservas_totales_periodo(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    return Reservation.objects.filter(
        date__range=[fecha_inicio, fecha_fin],
        estado='activa',
        **filt
    ).count()

# --- Reservas por pista ---
def reservas_por_pista(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    return list(
        Reservation.objects.filter(
            date__range=[fecha_inicio, fecha_fin],
            estado='activa',
            **filt
        ).values('court__name')
         .annotate(total=Count('id'))
         .order_by('-total')
    )

# --- Reservas por comunidad (acumulado) ---
def reservas_por_comunidad(fecha_inicio, fecha_fin):
    return list(
        Reservation.objects.filter(
            date__range=[fecha_inicio, fecha_fin],
            estado='activa'
        ).values('court__community__name')
         .annotate(total=Count('id'))
         .order_by('-total')
    )

# --- Ocupación por pista ---
def porcentaje_ocupacion_por_pista(fecha_inicio, fecha_fin, community_id=None):
    dias = (fecha_fin - fecha_inicio).days + 1
    courts = Court.objects.filter(community_id=community_id) if community_id else Court.objects.all()
    resultados = []
    for court in courts:
        n_slots = TimeSlot.objects.filter(court=court).count()
        slots_totales = n_slots * dias
        reservas = Reservation.objects.filter(
            court=court,
            date__range=[fecha_inicio, fecha_fin],
            estado='activa'
        ).count()
        ocupacion = (reservas / slots_totales * 100) if slots_totales else 0
        resultados.append({'pista': court.name, 'ocupacion_pct': round(ocupacion, 1)})
    return resultados

# --- Partidos jugados este mes y semana ---
def partidos_mes(community_id=None):
    hoy = date.today()
    filt = get_community_filter(community_id)
    return Reservation.objects.filter(
        date__year=hoy.year,
        date__month=hoy.month,
        estado='activa',
        **filt
    ).count()

def partidos_semana(community_id=None):
    hoy = date.today()
    filt = get_community_filter(community_id)
    qs = Reservation.objects.annotate(sem=TruncWeek('date')).filter(
        sem=TruncWeek(hoy),
        estado='activa',
        **filt
    )
    return qs.count()

# --- Ranking usuarios más activos ---
def ranking_usuarios_activos(fecha_inicio, fecha_fin, community_id=None, top=10):
    filt = get_community_filter(community_id)
    return list(
        Reservation.objects.filter(
            date__range=[fecha_inicio, fecha_fin],
            estado='activa',
            user__isnull=False,
            **filt
        )
        .values('user__email', 'user__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')[:top]
    )

# --- Proporción usuarios vs staff ---
def proporcion_usuarios_vs_staff(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    total = Reservation.objects.filter(date__range=[fecha_inicio, fecha_fin], estado='activa', **filt).count()
    staff = Reservation.objects.filter(date__range=[fecha_inicio, fecha_fin], estado='activa', user__is_staff=True, **filt).count()
    usuarios = total - staff if total >= staff else 0
    return {
        "total": total,
        "usuarios": usuarios,
        "staff": staff,
        "proporcion_staff_pct": round((staff / total) * 100, 1) if total else 0,
        "proporcion_usuarios_pct": round((usuarios / total) * 100, 1) if total else 0,
    }

# --- Invitaciones enviadas / aceptadas ---
def invitaciones_kpis(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    reservas_ids = Reservation.objects.filter(
        date__range=[fecha_inicio, fecha_fin],
        estado='activa',
        **filt
    ).values_list('id', flat=True)
    total_enviadas = ReservationInvitation.objects.filter(
        reserva_id__in=reservas_ids
    ).count()
    aceptadas = ReservationInvitation.objects.filter(
        reserva_id__in=reservas_ids, estado='aceptada'
    ).count()
    tasa = round((aceptadas / total_enviadas) * 100, 1) if total_enviadas else 0
    return {"enviadas": total_enviadas, "aceptadas": aceptadas, "tasa_aceptacion": tasa}

# --- Tasa de cancelaciones ---
def tasa_cancelaciones(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    totales = Reservation.objects.filter(date__range=[fecha_inicio, fecha_fin], estado='activa', **filt).count()
    canceladas = ReservationCancelada.objects.filter(date__range=[fecha_inicio, fecha_fin], **filt).count()
    suma = totales + canceladas
    tasa = round((canceladas / suma) * 100, 1) if suma else 0
    return {'total': totales, 'canceladas': canceladas, 'tasa': tasa}

# --- Reservas por franja horaria ---
def reservas_por_horario(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    return list(
        Reservation.objects.filter(
            date__range=[fecha_inicio, fecha_fin],
            estado='activa',
            timeslot__isnull=False,
            **filt
        ).values('timeslot__start_time', 'timeslot__end_time')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

# --- Participación media por partido ---
def participacion_media(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    reservas = Reservation.objects.filter(
        date__range=[fecha_inicio, fecha_fin],
        estado='activa',
        **filt
    )
    total_jugadores = 0
    total_partidos = reservas.count()
    for res in reservas:
        invitados = res.invitaciones.filter(estado='aceptada').count() if hasattr(res, 'invitaciones') else 0
        total_jugadores += 1 + invitados
    return round(total_jugadores / total_partidos, 2) if total_partidos else 0

# --- Nuevos usuarios registrados por periodo ---
def usuarios_nuevos(fecha_inicio, fecha_fin, community_id=None):
    if community_id:
        return Usuario.objects.filter(date_joined__date__range=[fecha_inicio, fecha_fin], community_id=community_id).count()
    return Usuario.objects.filter(date_joined__date__range=[fecha_inicio, fecha_fin]).count()

# --- Tiempo medio de antelación de las reservas ---
def tiempo_medio_antelacion(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    reservas = Reservation.objects.filter(
        date__range=[fecha_inicio, fecha_fin], 
        estado='activa', created_at__isnull=False, **filt
    )
    if not reservas.exists():
        return 0
    reservas = reservas.annotate(
        antelacion=ExpressionWrapper(
            F('date') - F('created_at'),
            output_field=DurationField()
        )
    )
    promedio = reservas.aggregate(promedio=Avg('antelacion'))['promedio']
    return round(promedio.total_seconds() / 86400, 2) if promedio else 0

# --- Cancelaciones de último minuto ---
def cancelaciones_ultimo_minuto(fecha_inicio, fecha_fin, community_id=None, horas=24):
    filt = get_community_filter(community_id)
    cancels = ReservationCancelada.objects.filter(
        date__range=[fecha_inicio, fecha_fin], **filt
    ).exclude(cancelada_at__isnull=True)
    total = cancels.count()
    if not total:
        return {'cancelaciones_ultimo_minuto': 0, 'total': 0, 'ratio_pct': 0}
    cancels = cancels.annotate(
        horas_antelacion=ExpressionWrapper(
            F('date') - F('cancelada_at'),
            output_field=DurationField()
        )
    )
    max_delta = timedelta(hours=horas)
    ult_minuto = cancels.filter(horas_antelacion__lte=max_delta).count()
    ratio = round((ult_minuto / total) * 100, 1) if total else 0
    return {'cancelaciones_ultimo_minuto': ult_minuto, 'total': total, 'ratio_pct': ratio}

# --- Participación por vivienda ---
def participacion_por_vivienda(fecha_inicio, fecha_fin, community_id=None):
    filt = get_community_filter(community_id)
    return list(
        Reservation.objects.filter(
            date__range=[fecha_inicio, fecha_fin],
            estado='activa',
            user__vivienda__isnull=False,
            **filt
        ).values('user__vivienda__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
