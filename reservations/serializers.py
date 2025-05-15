from rest_framework import serializers
from .models import Court, TimeSlot, Reservation
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'nombre'  # Indica que usas 'nombre' como USERNAME_FIELD

    def validate(self, attrs):
        # Valida usando 'nombre' en lugar de 'username'
        attrs[self.username_field] = attrs.get(self.username_field, "")
        return super().validate(attrs)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']  # Puedes ajustar los campos según lo que quieras exponer


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ('id', 'name')

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ('id', 'start_time', 'end_time')

class ReservationSerializer(serializers.ModelSerializer):
    
    timeslot = serializers.PrimaryKeyRelatedField(queryset=TimeSlot.objects.all())
    court = serializers.PrimaryKeyRelatedField(queryset=Court.objects.all())
    
    class Meta:
        model = Reservation
        fields = ('id', 'user', 'court', 'date', 'timeslot', 'created_at')
        read_only_fields = ['created_at', 'user']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'is_staff')