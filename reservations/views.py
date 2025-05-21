from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from .models import Court, TimeSlot, Reservation, Usuario, Vivienda, ReservationInvitation, InvitadoExterno
from .serializers import (
    CourtSerializer, TimeSlotSerializer, ReservationSerializer, UserSerializer,
    UsuarioSerializer, ReservationInvitationSerializer, WriteReservationSerializer
)
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.db import IntegrityError
from .serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django_filters import rest_framework as filters
from django.utils import timezone
from rest_framework import serializers
from django.core.mail import send_mail
from django.template.loader import render_to_string
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.exceptions import ValidationError

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

def obtener_viviendas(request):
    viviendas = list(Vivienda.objects.values('id', 'nombre'))
    return JsonResponse(viviendas, safe=False)

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

class ReservationFilter(filters.FilterSet):
    date = filters.DateFromToRangeFilter(field_name='date', lookup_expr='range')
    timeslot = filters.NumberFilter(field_name='timeslot__id')
    vivienda = filters.NumberFilter(field_name='user__vivienda__id')

    class Meta:
        model = Reservation
        fields = []

class ReservationViewSet(viewsets.ModelViewSet):
    parser_classes = [JSONParser]
    queryset = Reservation.objects.all().prefetch_related(
        'user__vivienda',
        'court',
        'timeslot',
        'invitaciones'
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
            
            # Obtener datos validados
            court = serializer.validated_data['court']
            timeslot = serializer.validated_data['timeslot']
            date = serializer.validated_data['date']

            # Validar reserva duplicada
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
            # Intercepta el error de conjunto único y tradúcelo
            non_field = e.detail.get('non_field_errors')
            if non_field and any("conjunto único" in str(msg) for msg in non_field):
                return Response({"error": "Este horario ya está reservado"}, status=status.HTTP_409_CONFLICT)
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Permitir borrar si es el propietario o staff
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
        print("Request data:", request.data)
        reserva = self.get_object()
        
        # Manejar formato antiguo y nuevo
        invitaciones_data = request.data.get('invitaciones', [])
        
        # Compatibilidad con versión anterior (emails y usuarios como listas separadas)
        if not invitaciones_data:
            emails = request.data.get('emails', [])
            usuarios_ids = request.data.get('usuarios', [])
            
            # Convertir a formato unificado
            invitaciones_data = [{"email": email} for email in emails]
            for user_id in usuarios_ids:
                usuario = Usuario.objects.filter(id=user_id).first()
                if usuario:
                    invitaciones_data.append({"email": usuario.email})

        # Validar límite de invitaciones
        total_invitaciones = reserva.invitaciones.count() + len(invitaciones_data)
        if total_invitaciones > 3:
            return Response(
                {"error": "Máximo 3 invitaciones por reserva"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Procesar cada invitación
        for data in invitaciones_data:
            try:
                email = data.get('email')
                if not email:
                    continue
                    
                print(f"Procesando invitación para: {email}")
                
                # Buscar usuario existente
                invitado_usuario = Usuario.objects.filter(email=email).first()
                
                # Obtener nombre histórico si existe
                invitacion_anterior = ReservationInvitation.objects.filter(email=email).first()
                nombre = data.get('nombre', "")
                nombre_final = nombre or getattr(invitacion_anterior, 'nombre_invitado', "") or email.split('@')[0]
                
                # IMPORTANTE: Guardar como InvitadoExterno para persistencia
                InvitadoExterno.objects.update_or_create(
                    usuario=request.user,
                    email=email,
                    defaults={'nombre': nombre_final}
                )
                
                # Crear invitación (manejar duplicados)
                invitacion, created = ReservationInvitation.objects.get_or_create(
                    reserva=reserva,
                    email=email,
                    defaults={
                        'invitado': invitado_usuario,
                        'nombre_invitado': nombre_final if not invitado_usuario else None
                    }
                )
                
                if created:
                    print(f"Invitación creada ID: {invitacion.id}")
                    self._enviar_email_invitacion(invitacion)
                else:
                    print(f"Invitación ya existente para {email}")

            except IntegrityError as e:
                print(f"Error de integridad: {str(e)}")
            except Exception as e:
                print(f"Error procesando invitación: {str(e)}")
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
        
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WriteReservationSerializer
        return ReservationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class UserViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = self.user.id
        data['username'] = self.user.username
        return data

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class ViviendaViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    def list(self, request):
        viviendas = Vivienda.objects.values('id', 'nombre')
        return Response(viviendas)

@api_view(['POST'])
def confirmar_invitacion(request, token):
    try:
        invitacion = ReservationInvitation.objects.get(token=token)
        invitacion.estado = 'aceptada' if request.data.get('aceptar') else 'rechazada'
        invitacion.save()
        return Response({"status": "Invitación actualizada"})
    except ReservationInvitation.DoesNotExist:
        return Response({"error": "Invitación no válida"}, status=404)

class UsuarioComunidadViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    def get_queryset(self):
        return Usuario.objects.exclude(id=self.request.user.id)\
            .select_related('vivienda')\
            .order_by('vivienda__nombre')

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

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
        
        # IMPORTANTE: Solo eliminamos la invitación, NO el InvitadoExterno
        invitacion.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class InvitadosFrecuentesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        # CAMBIADO: Ahora usa el modelo InvitadoExterno en lugar de ReservationInvitation
        invitados = InvitadoExterno.objects.filter(
            usuario=request.user
        ).values('email', 'nombre').distinct()
        
        # Formato compatible con el anterior
        resultado = [{'email': inv['email'], 'nombre_invitado': inv['nombre']} for inv in invitados]
        return Response(resultado)

# Nuevo endpoint para eliminar invitados externos
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
