from rest_framework import serializers
from .models import Court, TimeSlot, Reservation
from .models import Usuario, Vivienda
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import exceptions
from django.utils import timezone

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'  # Indica que usas 'nombre' como USERNAME_FIELD

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(
            request=self.context.get('request'),
            email=email,
            password=password
        )

        if not user:
            raise exceptions.AuthenticationFailed(
                {'error': 'Email o contraseña incorrectos'}
            )

        if not user.is_active:
            raise exceptions.AuthenticationFailed(
                {'error': 'Cuenta desactivada'}
            )

        data = super().validate(attrs)
        data.update({
            'user_id': self.user.id,
            'email': self.user.email,
            'user_id': self.user.id,
            'is_staff': self.user.is_staff,  # ← Añadido
            'nombre': self.user.nombre
        })
        return data


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ('id', 'name')

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ('id', 'start_time', 'end_time', 'slot')



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ('id', 'email', 'nombre', 'apellido', 'is_staff')
        
class ViviendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vivienda
        fields = ('id', 'nombre')

class UsuarioSerializer(serializers.ModelSerializer):
    vivienda = ViviendaSerializer(read_only=True)
    class Meta:
        model = Usuario
        fields = ('id', 'nombre', 'apellido', 'email', 'vivienda', 'is_staff')
        
 
class ReservationSerializer(serializers.ModelSerializer):
    user = UsuarioSerializer(read_only=True)        # Serializador anidado
    court = serializers.PrimaryKeyRelatedField(queryset=Court.objects.all())
    serializers.PrimaryKeyRelatedField(queryset=TimeSlot.objects.all())
    

    vivienda = serializers.SerializerMethodField()  # ← Nuevo campo

    class Meta:
        model = Reservation
        fields = ('id', 'user', 'court', 'date', 'timeslot', 'created_at', 'vivienda')
        read_only_fields = ['created_at', 'user']       
        
    def get_vivienda(self, obj):
        if obj.user and obj.user.vivienda:
            return obj.user.vivienda.nombre
        return None
    
    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("No se permiten reservas para fechas pasadas")
        return value