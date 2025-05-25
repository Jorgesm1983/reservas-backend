from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from .models import (
    Court, TimeSlot, Reservation, Usuario, Vivienda, ReservationInvitation, InvitadoExterno, Community
)
from .serializers import (
    CourtSerializer, TimeSlotSerializer, ReservationSerializer, UserSerializer,
    UsuarioSerializer, ReservationInvitationSerializer, WriteReservationSerializer,
    ViviendaSerializer, CustomTokenObtainPairSerializer, CommunitySerializer, ChangePasswordSerializer
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
    try:
        vivienda = Vivienda.objects.get(id=vivienda_id)
    except Vivienda.DoesNotExist:
        return JsonResponse({'error': 'Vivienda no existe'}, status=400)
    if Usuario.objects.filter(email=email).exists():
        return JsonResponse({'error': 'Email ya registrado'}, status=400)
    Usuario.objects.create_user(
        email=email,
        nombre=nombre,
        apellido=apellido,
        password=password,
        vivienda=vivienda
    )
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
                    
        total_invitaciones = reserva.invitaciones.count() + len(invitaciones_data)
        if total_invitaciones > 3:
            return Response(
                {"error": "Máximo 3 invitaciones por reserva"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        for data in invitaciones_data:
            try:
                email = data.get('email')
                if not email:
                    continue
                invitado_usuario = Usuario.objects.filter(email=email).first()
                invitacion_anterior = ReservationInvitation.objects.filter(reserva=reserva, email=email).first()
                nombre = data.get('nombre', "")
                nombre_final = (
                    nombre.strip()
                    if nombre and nombre.strip()
                    else (
                        invitacion_anterior.nombre_invitado
                        if invitacion_anterior and invitacion_anterior.nombre_invitado
                        else email.split('@')[0]
                    )
                )

                # Actualiza o crea InvitadoExterno SIEMPRE con el nombre recibido si no es vacío
                invitado_ext, created_ext = InvitadoExterno.objects.update_or_create(
                    usuario=request.user,
                    email=email,
                    defaults={'nombre': nombre_final}
                )
                # Si ya existe y el nombre recibido es no vacío y distinto, actualiza
                if (nombre and nombre.strip() and invitado_ext.nombre != nombre.strip()) or not invitado_ext.nombre:
                    invitado_ext.nombre = nombre.strip() or email.split('@')[0]
                    invitado_ext.save(update_fields=['nombre'])

                # Actualiza o crea ReservationInvitation SIEMPRE con el nombre recibido si no es vacío
                invitacion, created = ReservationInvitation.objects.get_or_create(
                    reserva=reserva,
                    email=email,
                    defaults={
                        'invitado': invitado_usuario,
                        'nombre_invitado': nombre_final
                    }
                )
                if (nombre and nombre.strip() and invitacion.nombre_invitado != nombre.strip()) or not invitacion.nombre_invitado:
                    invitacion.nombre_invitado = nombre.strip() or email.split('@')[0]
                    invitacion.save(update_fields=['nombre_invitado'])
                if created:
                    self._enviar_email_invitacion(invitacion)
            except IntegrityError:
                pass
            except Exception:
                return Response(
                    {"error": "Error al procesar invitaciones"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(
            {"status": "Invitaciones procesadas", "invitaciones_creadas": len(invitaciones_data)},
            status=status.HTTP_201_CREATED
        )

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
            'direccion_pista': invitacion.reserva.court.direccion if hasattr(invitacion.reserva.court, 'direccion') else "Consultar en recepción",
            'enlace_aceptar': f"https://tudominio.com/invitaciones/{invitacion.token}/aceptar/",
            'enlace_rechazar': f"https://tudominio.com/invitaciones/{invitacion.token}/rechazar/"
        }
        mensaje = render_to_string('emails/invitacion_reserva.txt', context)
        send_mail(
            subject='Invitación a partido de pádel',
            message=mensaje,
            from_email='notificaciones@tudominio.com',
            recipient_list=[invitacion.email],
            fail_silently=False
        )

# --- CRUD de usuarios (admin) ---
class UserViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')  # <--- Añade order_by aquí
    serializer_class = UsuarioSerializer  # <--- Debe ser este, no UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

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

@api_view(['POST'])
@permission_classes([AllowAny])
def solicitar_reset_password(request):
    email = request.data.get('email')
    try:
        user = Usuario.objects.get(email=email)
        # Generar token (usa tu lógica de tokens existente o django-rest-passwordreset)
        # Enviar email con el token (implementa esto según tu proveedor de email)
        return Response({"status": "Correo enviado"})
    except Usuario.DoesNotExist:
        return Response({"error": "Usuario no encontrado"}, status=404)
    
    
@api_view(['POST'])
@permission_classes([AllowAny])
def confirmar_reset_password(request):
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    # Validar token y cambiar contraseña
    # Implementa la lógica según tu sistema de tokens
    return Response({"status": "Contraseña actualizada"})

# --- CRUD de viviendas (admin y frontend) ---
class ViviendaViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        viviendas = Vivienda.objects.values('id', 'nombre')
        return Response(viviendas)

# --- CRUD de invitaciones ---
class ReservationInvitationViewSet(viewsets.ModelViewSet):
    queryset = ReservationInvitation.objects.all()
    serializer_class = ReservationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return ReservationInvitation.objects.all()
        return ReservationInvitation.objects.filter(reserva__user=user)

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

# --- CRUD de todas las reservas (admin) ---
class ReservationAllViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all().prefetch_related(
        'user__vivienda', 'court', 'timeslot', 'invitaciones'
    ).order_by('-date', 'timeslot__start_time')
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ReservationFilter

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WriteReservationSerializer
        return ReservationSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CommunityViewSet(viewsets.ModelViewSet):
    queryset = Community.objects.all()
    serializer_class = CommunitySerializer
    permission_classes = [permissions.IsAdminUser]  # Solo staff puede modificar