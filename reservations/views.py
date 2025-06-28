from rest_framework.views import APIView
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from django.db.models import OuterRef, Exists
from .models import (
    Court, TimeSlot, Reservation, Usuario, Vivienda, ReservationInvitation, InvitadoExterno, Community, ReservationCancelada
)
from .serializers import (
    CourtSerializer, TimeSlotSerializer, ReservationSerializer, UserSerializer,
    UsuarioSerializer, ReservationInvitationSerializer, WriteReservationSerializer,
    ViviendaSerializer, CustomTokenObtainPairSerializer, CommunitySerializer, ChangePasswordSerializer, InvitadoExternoSerializer
)
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from django.db import transaction, IntegrityError
from rest_framework.parsers import JSONParser
from django_filters import rest_framework as filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
import json
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from datetime import datetime, date
from django.utils import timezone

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

# import logging
# logger = logging.getLogger(__name__)


# --- Registro de usuario desde el frontend ---
@csrf_exempt
@require_POST
def registro_usuario(request):
    data = json.loads(request.body)
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    email = data.get('email')
    password = data.get('password')
    vivienda_id = data.get('vivienda_id')
    if not all([nombre, apellido, email, password, vivienda_id]):
        return JsonResponse({'error': 'Faltan datos'}, status=400)
    # Validación de formato de email
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'error': 'Formato de email no válido'}, status=400)
    try:
        vivienda = Vivienda.objects.get(id=vivienda_id)
    except Vivienda.DoesNotExist:
        return JsonResponse({'error': 'Vivienda no existe'}, status=400)
    if Usuario.objects.filter(email=email).exists():
        return JsonResponse({'error': 'Email ya registrado'}, status=400)
    usuario = Usuario.objects.create_user(
        email=email,
        nombre=nombre,
        apellido=apellido,
        password=password,
        vivienda=vivienda,
    )
    usuario.community = vivienda.community
    usuario.save()
    return JsonResponse({'message': 'Usuario registrado correctamente'})

# --- Listado de viviendas para el frontend ---
def obtener_viviendas(request):
    viviendas = list(Vivienda.objects.values('id', 'nombre'))
    return JsonResponse(viviendas, safe=False)

# --- CRUD de pistas ---
class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community')
        if user.is_staff and community_id:
            return Court.objects.filter(community_id=community_id)
        elif user.is_staff:
            return Court.objects.all()
        elif hasattr(user, 'community_id') and user.community_id:
            return Court.objects.filter(community_id=user.community_id)
        return Court.objects.none()

# --- CRUD de turnos ---
class TimeSlotViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community', None)
        
        user = self.request.user
        community_id = self.request.query_params.get('community', None)
        if user.is_staff and community_id:
            return TimeSlot.objects.filter(community_id=community_id)
        elif user.is_staff:
            return TimeSlot.objects.all()
        elif user.community:
            return TimeSlot.objects.filter(community=user.community)
        return TimeSlot.objects.none()

# --- Filtro para reservas ---
class ReservationFilter(filters.FilterSet):
    date = filters.DateFromToRangeFilter(field_name='date', lookup_expr='range')
    timeslot = filters.NumberFilter(field_name='timeslot__id')
    vivienda = filters.NumberFilter(field_name='user__vivienda__id')
    court = filters.NumberFilter(field_name='court__id')

    class Meta:
        model = Reservation
        fields = []


# --- CRUD de reservas (solo del usuario autenticado) ---
class ReservationViewSet(viewsets.ModelViewSet):
    parser_classes = [JSONParser]
    queryset = Reservation.objects.all().prefetch_related(
        'user__vivienda', 'court', 'timeslot', 'invitaciones'
    ).order_by('-date', 'timeslot__start_time')
    pagination_class = None
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ReservationFilter

    def get_queryset(self):
        return Reservation.objects.filter(user=self.request.user)\
            .prefetch_related('user__vivienda', 'court', 'timeslot', 'invitaciones')\
            .order_by('-date', 'timeslot__start_time')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WriteReservationSerializer
        return ReservationSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            court = serializer.validated_data['court']
            timeslot = serializer.validated_data['timeslot']
            date = serializer.validated_data['date']
            if Reservation.objects.filter(
                court=court,
                timeslot=timeslot,
                date=date
            ).exists():
                return Response(
                    {"error": "Este horario ya está reservado"},
                    status=status.HTTP_409_CONFLICT
                )
            reserva = serializer.save(user=request.user)
            read_serializer = ReservationSerializer(reserva, context={'request': request})
            return Response(read_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            non_field = e.detail.get('non_field_errors')
            if non_field and any("conjunto único" in str(msg) for msg in non_field):
                return Response({"error": "Este horario ya está reservado"}, status=status.HTTP_409_CONFLICT)
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "No tienes permiso para eliminar esta reserva"},
                status=status.HTTP_403_FORBIDDEN
            )
        self.perform_destroy(instance)
        return Response(
            {"success": "Reserva eliminada correctamente"},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(detail=True, methods=['post'])
    def invitar(self, request, pk=None):
        # print("==> Llamada a invitar")
        # print("Datos recibidos:", request.data)
        reserva = self.get_object()
        invitaciones_data = request.data.get('invitaciones', [])
        if not invitaciones_data:
            emails = request.data.get('emails', [])
            usuarios_ids = request.data.get('usuarios', [])
            invitaciones_data = [{"email": email} for email in emails]
            for user_id in usuarios_ids:
                usuario = Usuario.objects.filter(id=user_id).first()
                if usuario:
                    invitaciones_data.append({"email": usuario.email})
                    
        # Filtra solo las invitaciones activas (pendiente o aceptada)
        invitaciones_activas = reserva.invitaciones.filter(estado__in=["pendiente", "aceptada"]).count()
        total_invitaciones = invitaciones_activas + len(invitaciones_data)
        if total_invitaciones > 3:
            return Response(
                {"error": "Máximo 3 invitaciones por reserva"},
                status=status.HTTP_400_BAD_REQUEST
            )
                    
        for data in invitaciones_data:
            # print("\n=== Procesando invitación ===")
            # print("Datos recibidos:", data)
            try:
                email = data.get('email')
                # print("Email recibido:", email)
                if not email:
                    # print("No se encontró email, se omite esta invitación.")
                    continue

                invitado_usuario = Usuario.objects.filter(email=email).first()
                # print("Usuario encontrado:", invitado_usuario)

                invitacion_anterior = ReservationInvitation.objects.filter(reserva=reserva, email=email).first()
                # print("Invitación anterior:", invitacion_anterior)

                nombre = data.get('nombre', "")
                nombre_invitado = data.get('nombre_invitado', "")
                # print("Nombre recibido (nombre):", nombre)
                # print("Nombre recibido (nombre_invitado):", nombre_invitado)

                nombre_final = (
                    (nombre or nombre_invitado).strip()
                    if (nombre or nombre_invitado) and (nombre or nombre_invitado).strip()
                    else (
                        invitacion_anterior.nombre_invitado
                        if invitacion_anterior and invitacion_anterior.nombre_invitado
                        else email.split('@')[0]
                    )
                )
                # print("Nombre final usado:", nombre_final)

                # Actualiza o crea InvitadoExterno SIEMPRE con el nombre recibido si no es vacío
                invitado_ext, created_ext = InvitadoExterno.objects.update_or_create(
                    usuario=request.user,
                    email=email,
                    defaults={'nombre': nombre_final}
                )
                # print("InvitadoExterno creado/actualizado:", invitado_ext, "Creado:", created_ext)

                # Si ya existe y el nombre recibido es no vacío y distinto, actualiza
                if (nombre_final and invitado_ext.nombre != nombre_final) or not invitado_ext.nombre:
                    invitado_ext.nombre = nombre_final or email.split('@')[0]
                    invitado_ext.save(update_fields=['nombre'])
                    # print("Nombre de InvitadoExterno actualizado a:", invitado_ext.nombre)

                # Actualiza o crea ReservationInvitation SIEMPRE con el nombre recibido si no es vacío
                invitacion, created = ReservationInvitation.objects.get_or_create(
                    reserva=reserva,
                    email=email,
                    defaults={
                        'invitado': invitado_usuario,
                        'nombre_invitado': nombre_final
                    }
                )
                # print("ReservationInvitation creado/actualizado:", invitacion, "Creado:", created)

                if (nombre_final and invitacion.nombre_invitado != nombre_final) or not invitacion.nombre_invitado:
                    invitacion.nombre_invitado = nombre_final or email.split('@')[0]
                    invitacion.save(update_fields=['nombre_invitado'])
                    # print("Nombre de ReservationInvitation actualizado a:", invitacion.nombre_invitado)

                if created:
                    # print("Enviando email de invitación...")
                    self._enviar_email_invitacion(invitacion)
            except IntegrityError as e:
                # print("IntegrityError:", e)
                pass
            except Exception as e:
                # print("Excepción inesperada:", e)
                return Response(
                    {"error": "Error al procesar invitaciones", "detalle": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(
            {"status": "Invitaciones procesadas", "invitaciones_creadas": len(invitaciones_data)},
            status=status.HTTP_201_CREATED
        )
        # print("Invitación creada:", invitacion, "Creada:", created)
    def _enviar_email_invitacion(self, invitacion):
        invitacion.generar_token()
        context = {
            'convocante': invitacion.reserva.user.get_full_name() or invitacion.reserva.user.email,
            'nombre_invitado': invitacion.invitado.nombre if invitacion.invitado else invitacion.nombre_invitado or invitacion.email.split('@')[0],
            'reserva': invitacion.reserva,
            'pista': invitacion.reserva.court.name,
            'fecha': invitacion.reserva.date.strftime("%d/%m/%Y"),
            'hora_inicio': invitacion.reserva.timeslot.start_time,
            'hora_fin': invitacion.reserva.timeslot.end_time,
            'direccion_pista': invitacion.reserva.court.community.direccion if hasattr(invitacion.reserva.court, 'direccion') else "Consultar en recepción",
            'enlace_aceptar': f"https://tudominio.com/invitaciones/{invitacion.token}/aceptar/",
            'enlace_rechazar': f"https://tudominio.com/invitaciones/{invitacion.token}/rechazar/"
        }
        mensaje = render_to_string('emails/invitacion_reserva.txt', context)
        send_mail(
            subject='Invitación a partido de pádel',
            message=mensaje,
            from_email=None,
            recipient_list=[invitacion.email],
            fail_silently=False
        )

# --- CRUD de usuarios (admin) ---
class UserViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')  # <--- Añade order_by aquí
    serializer_class = UsuarioSerializer  # <--- Debe ser este, no UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    
    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community')
        if user.is_staff and community_id:
            return Usuario.objects.filter(community_id=community_id)
        elif user.is_staff:
            return Usuario.objects.all()
        elif hasattr(user, 'community_id') and user.community_id:
            return Usuario.objects.filter(community_id=user.community_id)
        return Usuario.objects.none()

# --- CRUD de usuarios (frontend) ---
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
      
    @action(detail=True, methods=['post'])
    def cambiar_password(self, request, pk=None):
        usuario = self.get_object()
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            usuario.set_password(serializer.validated_data['new_password'])
            usuario.save()
            return Response({"status": "Contraseña actualizada"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# --- CRUD de viviendas (admin y frontend) ---
class ViviendaViewSet(viewsets.ModelViewSet):
    queryset = Vivienda.objects.all()
    serializer_class = ViviendaSerializer
    permission_classes = [AllowAny]
    pagination_class = None
       
    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community')
        if user.is_staff and community_id:
            return Vivienda.objects.filter(community_id=community_id)
        elif user.is_staff:
            return Vivienda.objects.all()
        elif hasattr(user, 'community_id') and user.community_id:
            return Vivienda.objects.filter(community_id=user.community_id)
        return Vivienda.objects.none()

# --- CRUD de invitaciones ---
class ReservationInvitationViewSet(viewsets.ModelViewSet):
    queryset = ReservationInvitation.objects.all().order_by('-fecha_invitacion', '-id')
    serializer_class = ReservationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]


    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community')
        qs = ReservationInvitation.objects.select_related('reserva__court')
        if user.is_staff and community_id:
            return qs.filter(reserva__court__community_id=community_id)
        elif user.is_staff:
            return qs
        elif hasattr(user, 'community_id') and user.community_id:
            return qs.filter(reserva__court__community_id=user.community_id)
        return qs.none()
    

    def destroy(self, request, *args, **kwargs):
        invitacion = self.get_object()
        if invitacion.reserva.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "No tienes permiso para eliminar esta invitación"},
                status=status.HTTP_403_FORBIDDEN
            )
        invitacion.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# --- Invitados frecuentes ---
class InvitadosFrecuentesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        invitados = InvitadoExterno.objects.filter(
            usuario=request.user
        ).values('email', 'nombre').distinct()
        resultado = [{'email': inv['email'], 'nombre_invitado': inv['nombre']} for inv in invitados]
        return Response(resultado)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def eliminar_invitado_externo(request, email):
    try:
        invitado = InvitadoExterno.objects.get(
            usuario=request.user,
            email=email
        )
        invitado.delete()
        return Response(
            {"status": "Invitado externo eliminado correctamente"},
            status=status.HTTP_200_OK
        )
    except InvitadoExterno.DoesNotExist:
        return Response({"error": "Invitado no encontrado"}, status=404)


# --- Listado de usuarios de la comunidad (para invitaciones) ---
class UsuarioComunidadViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    def get_queryset(self):
        return Usuario.objects.exclude(id=self.request.user.id)\
            .select_related('vivienda')\
            .order_by('vivienda__nombre')

# --- Vista personalizada para login con JWT ---
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = self.user.id
        data['username'] = self.user.username
        return data

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# --- Confirmar invitación ---
@api_view(['POST'])
def confirmar_invitacion(request, token):
    try:
        invitacion = ReservationInvitation.objects.get(token=token)
        invitacion.estado = 'aceptada' if request.data.get('aceptar') else 'rechazada'
        invitacion.save()
        return Response({"status": "Invitación actualizada"})
    except ReservationInvitation.DoesNotExist:
        return Response({"error": "Invitación no válida"}, status=404)





class ReservationAllViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all().prefetch_related(
        'user__vivienda', 'court', 'timeslot', 'invitaciones'
    ).order_by('-date', 'timeslot__start_time')
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ReservationFilter
    
    import logging
    logger = logging.getLogger(__name__)
    
    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community')
        qs = Reservation.objects.select_related('user', 'court__community', 'timeslot').prefetch_related('invitaciones')
        if user.is_staff and community_id:
            return qs.filter(court__community_id=community_id)
        elif user.is_staff:
            return qs
        elif hasattr(user, 'community_id') and user.community_id:
            return qs.filter(court__community_id=user.community_id)
        return qs.none()


    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WriteReservationSerializer
        return ReservationSerializer

    def perform_create(self, serializer):
        self._assign_user(serializer)
        
    def perform_update(self, serializer):
        self._assign_user(serializer)
        
    def _assign_user(self, serializer):
        """Asigna usuario según permisos"""
        user = self.request.user
        if user.is_staff and 'user' in self.request.data:
            serializer.save(user_id=self.request.data['user'])
        else:
            serializer.save(user=user)      
        
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        ReservationCancelada.objects.create(
            user=instance.user,
            court=instance.court,
            timeslot=instance.timeslot,
            date=instance.date,
            created_at=instance.created_at,
            cancelada_at=timezone.now()
        )
        instance.delete()  # Elimina la reserva original
        return Response({'status': 'cancelada'}, status=200)

class CommunityViewSet(viewsets.ModelViewSet):
    queryset = Community.objects.all()
    serializer_class = CommunitySerializer
    permission_classes = [permissions.IsAdminUser]  # Solo staff puede modificar
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    user = request.user

    # Partidos jugados este mes
    now = datetime.now()
    partidos_jugados = Reservation.objects.filter(
        user=user,
        date__month=now.month,
        date__year=now.year
    ).count()

    # Invitaciones pendientes
    invitaciones_pendientes = ReservationInvitation.objects.filter(
        invitado=user, estado='pendiente'
    ).select_related('reserva__court', 'reserva__timeslot', 'reserva__user')
    invitaciones_serializadas = ReservationInvitationSerializer(invitaciones_pendientes, many=True).data

    return Response({
        "nombre": user.nombre,
        "partidos_jugados_mes": partidos_jugados,
        "invitaciones_pendientes": invitaciones_serializadas,
        "is_staff": user.is_staff,
    })
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def proximos_partidos_invitado(request):
    user = request.user
    hoy = date.today()
    invitaciones_aceptadas = ReservationInvitation.objects.filter(
        invitado=user,
        estado='aceptada',
        reserva__date__gte=hoy
    ).select_related('reserva')
    reservas = [inv.reserva for inv in invitaciones_aceptadas]
    data = ReservationSerializer(reservas, many=True).data
    return Response(data)

class AceptarInvitacionView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, token):
        try:
            invitacion = ReservationInvitation.objects.get(token=token)
            if invitacion.estado == "aceptada":
                return Response({"detail": "La invitación ya fue aceptada."}, status=200)
            invitacion.estado = "aceptada"
            invitacion.save()
            return Response({"detail": "Invitación aceptada correctamente."}, status=200)
        except ReservationInvitation.DoesNotExist:
            return Response({"detail": "Invitación no encontrada."}, status=404)
        
class RechazarInvitacionView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, token):
        try:
            invitacion = ReservationInvitation.objects.get(token=token)
            if invitacion.estado == "rechazada":
                return Response({"detail": "La invitación ya fue rechazada."}, status=200)
            invitacion.estado = "rechazada"
            invitacion.save()
            return Response({"detail": "Invitación rechazada correctamente."}, status=200)
        except ReservationInvitation.DoesNotExist:
            return Response({"detail": "Invitación no encontrada."}, status=404)
        
class InvitadoExternoViewSet(viewsets.ModelViewSet):
    serializer_class = InvitadoExternoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'email'
    lookup_value_regex = '[^/]+'  # Permite emails con puntos, ñ, etc.
    pagination_class = None
    
    def get_queryset(self):
        user = self.request.user
        community_id = self.request.query_params.get('community')
        qs = InvitadoExterno.objects.all()
        from .models import Usuario

        if user.is_staff:
            if community_id:
                # Invitados externos de esa comunidad cuyo email NO está en usuarios de esa comunidad
                user_qs = Usuario.objects.filter(email=OuterRef('email'), community_id=community_id)
                return qs.filter(usuario__community_id=community_id)\
                         .annotate(es_usuario=Exists(user_qs))\
                         .filter(es_usuario=False)
            else:
                # Invitados externos de cualquier comunidad cuyo email NO está en usuarios de ninguna comunidad
                user_qs = Usuario.objects.filter(email=OuterRef('email'))
                return qs.annotate(es_usuario=Exists(user_qs)).filter(es_usuario=False)
        elif hasattr(user, 'community_id') and user.community_id:
            # Invitados externos de la comunidad del usuario cuyo email NO está en usuarios de esa comunidad
            user_qs = Usuario.objects.filter(email=OuterRef('email'), community_id=user.community_id)
            return qs.filter(usuario__community_id=user.community_id)\
                     .annotate(es_usuario=Exists(user_qs))\
                     .filter(es_usuario=False)
        else:
            return qs.none()
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ocupados(request):
    court_id = request.GET.get('court')
    date = request.GET.get('date_after')
    if not court_id or not date:
        return Response({"error": "Parámetros 'court' y 'date_after' requeridos."}, status=400)
    ocupados = Reservation.objects.filter(
        court_id=court_id,
        date=date
    ).values_list('timeslot_id', flat=True)
    return Response(list(ocupados))

@api_view(['POST'])
@permission_classes([AllowAny])
def viviendas_por_codigo(request):
    codigo = request.data.get('codigo')
    try:
        comunidad = Community.objects.get(code=codigo)
    except Community.DoesNotExist:
        return Response({'error': 'Código de comunidad no válido'}, status=400)
    viviendas = Vivienda.objects.filter(community=comunidad)
    data = [{'id': v.id, 'nombre': v.nombre} for v in viviendas]
    return Response({
        'viviendas': data,
        'comunidad_nombre': comunidad.name  # <-- Añade esto
    })