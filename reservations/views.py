from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Court, TimeSlot, Reservation
from .serializers import CourtSerializer, TimeSlotSerializer, ReservationSerializer, UserSerializer
from django.contrib.auth.models import User
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.db import transaction

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    def get_permissions(self):
        # Solo admins pueden crear/editar/borrar
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            # Cualquier autenticado puede ver
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Extraer datos de la reserva
        court_id = request.data.get('court')
        timeslot_id = request.data.get('timeslot')
        date = request.data.get('date')

        # Verificar si ya existe una reserva para esta combinación
        if Reservation.objects.filter(
            court=court_id,
            timeslot=timeslot_id,
            date=date
        ).exists():
            return Response(
                {
                    "error": "Este horario ya está reservado para la pista seleccionada",
                    "detail": "Por favor, elige otra fecha, hora o pista"
                },
                status=status.HTTP_409_CONFLICT
            )

        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_create(self, serializer):
        # Asignación automática del usuario autenticado
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Verificar permisos de cancelación
        if not (request.user == instance.user or request.user.is_staff):
            return Response(
                {"error": "No tienes permiso para cancelar esta reserva"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        self.perform_destroy(instance)
        return Response(
            {"success": "Reserva cancelada correctamente"},
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