from rest_framework import serializers
from .models import Court, TimeSlot, Reservation
from django.contrib.auth.models import User

class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ('id', 'name')

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ('id', 'start_time', 'end_time')

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ('id', 'user', 'court', 'date', 'slot')
        read_only_fields = ['id', 'user']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'is_staff')