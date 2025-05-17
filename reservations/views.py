from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Court, TimeSlot, Reservation, Usuario, Vivienda
from .serializers import CourtSerializer, TimeSlotSerializer, ReservationSerializer, UserSerializer
from django.contrib.auth import get_user_model
User = get_user_model()
from rest_framework.permissions import IsAdminUser, IsAuthenticated
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
from rest_framework.permissions import AllowAny

@csrf_exempt
@require_POST
def registro_usuario(request):
    data = json.loads(request.body)
    nombre = data.get('nombre')  # ← Nuevo campo
    apellido = data.get('apellido')
    email = data.get('email')
    password = data.get('password')
    vivienda_id = data.get('vivienda_id')
    
    # Validación de datos
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

# Nueva vista para obtener viviendas
def obtener_viviendas(request):
    viviendas = list(Vivienda.objects.values('id', 'nombre'))
    return JsonResponse(viviendas, safe=False)

class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    pagination_class = None  # ← Desactiva paginación
    def get_permissions(self):
        # Solo admins pueden crear/editar/borrar
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            # Cualquier autenticado puede ver
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]


class TimeSlotViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    pagination_class = None  # ← Desactiva la paginación
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]



class ReservationFilter(filters.FilterSet):
    date = filters.DateFromToRangeFilter(field_name='date', lookup_expr='range') 
    timeslot = filters.NumberFilter(field_name='timeslot__id')  # ← Corregido
    vivienda = filters.NumberFilter(field_name='user__vivienda__id')  
    class Meta:
        model = Reservation
        fields = []

class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all().prefetch_related(
        'user__vivienda',
        'court',
        'timeslot'
    ).order_by('-date', 'timeslot__start_time')
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ReservationFilter
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset  # ← No sobreescribir el queryset aquí

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            if not request.user.vivienda:
                return Response(
                    {"error": "El usuario debe tener una vivienda asignada"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validar fecha
            date = serializer.validated_data['date']
            if date < timezone.localdate():
                return Response(
                    {"error": "No se permiten reservas para fechas pasadas"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verificar duplicados usando datos validados
            if Reservation.objects.filter(
                court=serializer.validated_data['court'],
                timeslot=serializer.validated_data['timeslot'],
                date=date
            ).exists():
                return Response(
                    {"error": "Este horario ya está reservado"},
                    status=status.HTTP_409_CONFLICT
                )

                # Crear reserva
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)        

        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {"error": "Acceso denegado: Se requieren privilegios de administrador"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"success": "Reserva eliminada correctamente"},
            status=status.HTTP_204_NO_CONTENT
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
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
    