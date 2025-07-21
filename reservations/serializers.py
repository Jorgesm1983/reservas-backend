from rest_framework import serializers
from .models import Court, TimeSlot, Reservation, ReservationInvitation
from .models import Usuario, Vivienda, Community, InvitadoExterno
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import exceptions
from django.utils import timezone
from reservations.models import TimeSlot
from rest_framework.validators import UniqueTogetherValidator
from django.contrib.auth.password_validation import validate_password
from datetime import datetime

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
            'is_staff': self.user.is_staff,
	      # ← Añadido
            'nombre': self.user.nombre
        })
        return data

class CommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ['id', 'name', 'direccion', 'code', 'reserva_hora_apertura_pasado', 'reserva_max_dias']

class CourtSerializer(serializers.ModelSerializer):
    comunidad_nombre = serializers.CharField(source='community.name', read_only=True)
    comunidad_direccion = serializers.CharField(source='community.direccion', read_only=True)
    community_id = serializers.PrimaryKeyRelatedField(
        queryset=Community.objects.all(),
        source='community',
        write_only=True,
        required=True
    )
    reserva_hora_apertura_pasado = serializers.SerializerMethodField()
    reserva_max_dias = serializers.SerializerMethodField()

    class Meta:
        model = Court
        fields = [
            'id', 'name', 'community', 'comunidad_nombre', 'comunidad_direccion',
            'community_id', 'reserva_hora_apertura_pasado', 'reserva_max_dias'
        ]

    def get_reserva_hora_apertura_pasado(self, obj):
        # Si la pista tiene valor, úsalo; si no, usa el de la comunidad
        if obj.reserva_hora_apertura_pasado is not None:
            return obj.reserva_hora_apertura_pasado
        if obj.community and obj.community.reserva_hora_apertura_pasado is not None:
            return obj.community.reserva_hora_apertura_pasado
        return None

    def get_reserva_max_dias(self, obj):
        if obj.reserva_max_dias is not None:
            return obj.reserva_max_dias
        if obj.community and obj.community.reserva_max_dias is not None:
            return obj.community.reserva_max_dias
        return None


# class CourtSerializer(serializers.ModelSerializer):
    
#     comunidad_nombre = serializers.CharField(source='community.name', read_only=True)
#     comunidad_direccion = serializers.CharField(source='community.direccion', read_only=True)
#     community_id = serializers.PrimaryKeyRelatedField(
#         queryset=Community.objects.all(),
#         source='community',
#         write_only=True,
#         required=True
#     )
#     reserva_hora_apertura_pasado = serializers.TimeField(required=False)
#     reserva_max_dias = serializers.IntegerField(required=False)
    
#     class Meta:
#         model = Court
#         fields = [
#             'id', 'name', 'community', 'comunidad_nombre', 'comunidad_direccion',
#             'community_id', 'reserva_hora_apertura_pasado', 'reserva_max_dias'
#         ]

class TimeSlotSerializer(serializers.ModelSerializer):
    court = CourtSerializer(read_only=True)
    courtid = serializers.PrimaryKeyRelatedField(queryset=Court.objects.all(), source='court', write_only=True)
    class Meta:
        model = TimeSlot
        fields = ['id', 'slot', 'start_time', 'end_time', 'court', 'courtid']

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
    
    # NUEVOS para WhatsApp/email:
    convocante = serializers.SerializerMethodField()
    pista = serializers.SerializerMethodField()
    direccion_pista = serializers.SerializerMethodField()
    fecha = serializers.SerializerMethodField()
    hora_inicio = serializers.SerializerMethodField()
    hora_fin = serializers.SerializerMethodField()
    enlace_aceptar = serializers.SerializerMethodField()
    enlace_rechazar = serializers.SerializerMethodField()

    class Meta:
        model = ReservationInvitation
        fields = [
            'id', 'reserva', 'invitado', 'email', 'estado', 'token',
            'fecha_invitacion', 'nombre_invitado', 'nombre_mostrar',
            'convocante', 'pista', 'direccion_pista', 'fecha',
            'hora_inicio', 'hora_fin', 'enlace_aceptar', 'enlace_rechazar'
        ]

    def get_convocante(self, obj):
        return obj.reserva.user.get_full_name() if obj.reserva and obj.reserva.user else None

    def get_pista(self, obj):
        return obj.reserva.court.name if obj.reserva and obj.reserva.court else None

    def get_direccion_pista(self, obj):
        if obj.reserva and obj.reserva.court and obj.reserva.court.community:
            return obj.reserva.court.community.direccion or "Consultar en recepción"
        return "Consultar en recepción"

    def get_fecha(self, obj):
        return obj.reserva.date.strftime("%d/%m/%Y") if obj.reserva and obj.reserva.date else None

    def get_hora_inicio(self, obj):
        return obj.reserva.timeslot.start_time.strftime("%H:%M") if obj.reserva and obj.reserva.timeslot else None

    def get_hora_fin(self, obj):
        return obj.reserva.timeslot.end_time.strftime("%H:%M") if obj.reserva and obj.reserva.timeslot else None

    def get_enlace_aceptar(self, obj):
        return f"https://www.pistareserva.com/invitaciones/{obj.token}/aceptar/" if obj.token else None

    def get_enlace_rechazar(self, obj):
        return f"https://www.pistaresera.com/invitaciones/{obj.token}/rechazar/" if obj.token else None
    
    
    def get_nombre_mostrar(self, obj):
        if obj.invitado:
            return getattr(obj.invitado, 'get_full_name', lambda: None)() or getattr(obj.invitado, 'nombre', None) or obj.invitado.email
        return obj.nombre_invitado or obj.email
        
class ViviendaSerializer(serializers.ModelSerializer):
    community = CommunitySerializer(read_only=True)
    community_id = serializers.PrimaryKeyRelatedField(
        queryset=Community.objects.all(),
        source='community',
        write_only=True,
        required=True
    )

    class Meta:
        model = Vivienda
        fields = ['id', 'nombre', 'community', 'community_id']

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
    codigo_comunidad = serializers.CharField(write_only=True, required=False)
    accepted_terms = serializers.BooleanField(write_only=True)
    terms_accepted_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Usuario
        fields = (
            'id', 'nombre', 'apellido', 'email', 
            'is_staff', 'vivienda', 'community',
            'vivienda_id', 'community_id', 'codigo_comunidad', 'accepted_terms', 'terms_accepted_at'
        )

    
    def validate(self, data):
    # Obtiene la comunidad por ID o por código
        comunidad = data.get('community') or data.get('community_id')
        codigo = data.get('codigo_comunidad')
        vivienda = data.get('vivienda')

        if not comunidad:
        # Si no hay comunidad explícita, exige el código
            if not codigo:
                raise serializers.ValidationError({'codigo_comunidad': 'Este campo es obligatorio'})
            try:
                comunidad = Community.objects.get(code=codigo)
            except Community.DoesNotExist:
                raise serializers.ValidationError({'codigo_comunidad': 'Código de comunidad no válido'})
            data['community'] = comunidad

    # Validar vivienda si se proporciona
        if vivienda and comunidad and vivienda.community != comunidad:
            raise serializers.ValidationError({'vivienda_id': 'La vivienda no pertenece a la comunidad seleccionada'})
        return data

    def create(self, validated_data):
        validated_data.pop('codigo_comunidad', None)
        accepted_terms = validated_data.pop('accepted_terms', False)
        if not accepted_terms:
            raise serializers.ValidationError({'accepted_terms': 'Debes aceptar los términos y condiciones.'})
        validated_data['accepted_terms'] = True
        validated_data['terms_accepted_at'] = timezone.now()
        return super().create(validated_data)
        
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
    user = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all(), required=False)
    

    class Meta:
        model = Reservation
        fields = ('user', 'court', 'timeslot', 'date')
        validators = [
            UniqueTogetherValidator(
                queryset=Reservation.objects.all(),
                fields=['court', 'timeslot', 'date'],
                message="Este horario ya está reservado"
            )
        ]
        
    def validate(self, data):
        court = data.get('court')
        timeslot = data.get('timeslot')
        date = data.get('date')
        user = data.get('user') or self.context['request'].user

        # Validación de turno y pista
        if timeslot.court != court:
            raise serializers.ValidationError({
                'timeslot': 'El turno seleccionado no pertenece a la pista seleccionada.'
            })

        # Obtén reglas de la pista o comunidad
        hora_apertura = court.reserva_hora_apertura_pasado or court.community.reserva_hora_apertura_pasado
        max_dias = court.reserva_max_dias if court.reserva_max_dias is not None else court.community.reserva_max_dias

        now = datetime.now()
        hoy = now.date()
        dias_diferencia = (date - hoy).days

        # No permitir fechas pasadas
        if dias_diferencia < 0:
            raise serializers.ValidationError("No puedes reservar para fechas pasadas.")

        # No permitir más allá del máximo configurado
        if dias_diferencia > max_dias:
            raise serializers.ValidationError(f"Solo puedes reservar hasta {max_dias} días vista.")

        # Para el último día permitido, solo a partir de la hora de apertura
        if dias_diferencia == max_dias and now.time() < hora_apertura:
            hora_str = hora_apertura.strftime("%H:%M")
            raise serializers.ValidationError(f"Las reservas para ese día se abren a partir de las {hora_str}.")

        vivienda = getattr(user, 'vivienda', None)
        if vivienda:
            qs = Reservation.objects.filter(user__vivienda=vivienda, date=date)
            # Excluir la propia reserva si es edición
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Solo puede haber una reserva por vivienda y día."
                )
        return data


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance
    
class InvitadoExternoSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    usuario_id = serializers.IntegerField(source='usuario.id', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    usuario_email = serializers.CharField(source='usuario.email', read_only=True)

    class Meta:
        model = InvitadoExterno
        fields = ['id', 'email', 'nombre','usuario_id', 'usuario_nombre', 'usuario_email']
