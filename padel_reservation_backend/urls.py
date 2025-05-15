from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.contrib import admin
from reservations.views import (
    CourtViewSet, TimeSlotViewSet,
    ReservationViewSet, UserViewSet,
    CustomLoginView, registro_usuario, obtener_viviendas
)
from rest_framework_simplejwt.views import TokenRefreshView
from reservations.serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer  # Usa tu serializador
    
    

router = DefaultRouter()
router.register(r'courts', CourtViewSet)
router.register(r'timeslots', TimeSlotViewSet)
router.register(r'reservations', ReservationViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/login/', CustomLoginView.as_view(), name='api-login'),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/registro_usuario', registro_usuario),
    path('api/obtener_viviendas', obtener_viviendas),
]