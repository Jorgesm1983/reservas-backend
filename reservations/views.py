from rest_framework import viewsets
from .models import Court, TimeSlot, Reservation
from .serializers import CourtSerializer, TimeSlotSerializer, ReservationSerializer, UserSerializer
from django.contrib.auth.models import User
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CourtViewSet(viewsets.ModelViewSet):
    queryset = Court.objects.all()
    serializer_class = CourtSerializer
    permission_classes = [IsAdminUser]  # Solo admins pueden crear/editar


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAdminUser]


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        print("📩 Datos entrantes a ReservationViewSet:", request.data)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # print("Datos de la reserva: ", serializer.validated_data)
        # Fuerza a que la reserva se asocie al usuario autenticado
        serializer.save(user=self.request.user)


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