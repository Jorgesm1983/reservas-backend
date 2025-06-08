from rest_framework import serializers
from .models import Court, TimeSlot, Reservation, ReservationInvitation
from .models import Usuario, Vivienda, Community
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import exceptions
from django.utils import timezone
from reservations.models import TimeSlot
from rest_framework.validators import UniqueTogetherValidator
from django.contrib.auth.password_validation import validate_password


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
        fields = ('id', 'name', 'direccion')

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ('id', 'start_time', 'end_time', 'slot')

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ('id', 'email', 'nombre', 'apellido', 'is_staff')

class SimpleReservationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    court = CourtSerializer(read_only=True)
    timeslot = TimeSlotSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = ('id', 'user', 'court', 'date', 'timeslot', 'created_at')

class ReservationInvitationSerializer(serializers.ModelSerializer):
    nombre_mostrar = serializers.SerializerMethodField()
    reserva = SimpleReservationSerializer(read_only=True)

    class Meta:
        model = ReservationInvitation
        fields = [
            'id', 'reserva', 'invitado', 'email', 'estado', 'token',
            'fecha_invitacion', 'nombre_invitado', 'nombre_mostrar'
        ]

    def get_nombre_mostrar(self, obj):
        if obj.invitado:
            return getattr(obj.invitado, 'get_full_name', lambda: None)() or getattr(obj.invitado, 'nombre', None) or obj.invitado.email
        return obj.nombre_invitado or obj.email
        
class ViviendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vivienda
        fields = ('id', 'nombre')

class CommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ['id', 'name']

class UsuarioSerializer(serializers.ModelSerializer):
    vivienda = ViviendaSerializer(read_only=True)
    community = CommunitySerializer(read_only=True)
    vivienda_id = serializers.PrimaryKeyRelatedField(
        queryset=Vivienda.objects.all(), 
        source='vivienda', 
        write_only=True, 
        required=False,
        allow_null=True
    )
    community_id = serializers.PrimaryKeyRelatedField(
        queryset=Community.objects.all(),
        source='community',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Usuario
        fields = (
            'id', 'nombre', 'apellido', 'email', 
            'is_staff', 'vivienda', 'community',
            'vivienda_id', 'community_id'
        )
    
    def get_vivienda(self, obj):
        return obj.vivienda.nombre if obj.vivienda else None
        
class ReservationSerializer(serializers.ModelSerializer):
    user = UsuarioSerializer(read_only=True)
    court = CourtSerializer(read_only=True)
    timeslot = TimeSlotSerializer(read_only=True)
    invitaciones = ReservationInvitationSerializer(many=True, read_only=True)
    estado = serializers.CharField()  # ← Añade este campo
    

    vivienda = serializers.SerializerMethodField()  # ← Nuevo campo

    class Meta:
        model = Reservation
        fields = ('id', 'user', 'court', 'date', 'timeslot', 'created_at', 'vivienda', 'invitaciones', 'estado')
        read_only_fields = ['created_at', 'user']       
        
    def get_vivienda(self, obj):
        if obj.user and obj.user.vivienda:
            return obj.user.vivienda.nombre
        return None
    
    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("No se permiten reservas para fechas pasadas")
        return value
    
class WriteReservationSerializer(serializers.ModelSerializer):
    court = serializers.PrimaryKeyRelatedField(queryset=Court.objects.all())
    timeslot = serializers.PrimaryKeyRelatedField(queryset=TimeSlot.objects.all())

    class Meta:
        model = Reservation
        fields = ('court', 'timeslot', 'date')
        validators = [
            UniqueTogetherValidator(
                queryset=Reservation.objects.all(),
                fields=['court', 'timeslot', 'date'],
                message="Este horario ya está reservado"
            )
        ]

class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance