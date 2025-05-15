from rest_framework import serializers
from .models import Court, TimeSlot, Reservation
from django.contrib.auth.models import User


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
    
    timeslot = TimeSlotSerializer(read_only=True)  # ← Serializador anidado
    user = UserSerializer(read_only=True)          # ← Serializador anidado
    
    class Meta:
        model = Reservation
        fields = ('id', 'user', 'court', 'date', 'timeslot', 'created_at')
        read_only_fields = ['created_at', 'user']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'is_staff')