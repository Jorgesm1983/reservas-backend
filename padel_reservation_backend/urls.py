from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.contrib import admin

from reservations.views import (
    CourtViewSet, TimeSlotViewSet,
    ReservationViewSet, UserViewSet,
    CustomLoginView, registro_usuario, obtener_viviendas, confirmar_invitacion, UsuarioComunidadViewSet,
    UsuarioViewSet, ReservationInvitationViewSet, confirmar_invitacion, ViviendaViewSet, InvitadosFrecuentesViewSet, eliminar_invitado_externo, ReservationAllViewSet, 
    CommunityViewSet, user_dashboard, proximos_partidos_invitado, AceptarInvitacionView, RechazarInvitacionView, InvitadoExternoViewSet, get_ocupados, viviendas_por_codigo)
from rest_framework_simplejwt.views import TokenRefreshView
from reservations.serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from reservations.admin import estadisticas_dashboard_view




class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer  # Usa tu serializador
    
    



router = DefaultRouter()
router.register(r'courts', CourtViewSet)
router.register(r'timeslots', TimeSlotViewSet)
router.register(r'mis-reservas', ReservationViewSet, basename='mis-reservas')
router.register(r'reservations', ReservationAllViewSet, basename='reservations')
router.register(r'users', UserViewSet)
router.register(r'usuarios-comunidad', UsuarioComunidadViewSet, basename='usuarios-comunidad')
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')
router.register(r'invitaciones', ReservationInvitationViewSet, basename='invitaciones')
router.register(r'viviendas', ViviendaViewSet, basename = 'vivienda')
router.register(r'invitaciones-frecuentes', InvitadosFrecuentesViewSet, basename='invitaciones-frecuentes')
router.register(r'comunidades', CommunityViewSet, basename='comunidades')
router.register(r'invitados-externos', InvitadoExternoViewSet, basename='invitadoexterno')

urlpatterns = [
    path('django-admin/estadisticas/', estadisticas_dashboard_view, name='estadisticas-dashboard'),
    path('django-admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/login/', CustomLoginView.as_view(), name='api-login'),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/registro_usuario', registro_usuario),
    path('api/obtener_viviendas', obtener_viviendas),
    # path('confirmar-invitacion/<str:token>/', confirmar_invitacion, name='confirmar-invitacion'),
    path('api/invitaciones/<str:token>/', confirmar_invitacion, name='confirmar-invitacion'),
    path('api/invitados-externos/<str:email>/', eliminar_invitado_externo),

    path('api/dashboard/', user_dashboard, name='user-dashboard'), 
    path('api/confirmar_invitacion/<str:token>/', confirmar_invitacion, name='confirmar_invitacion'),  
    path('api/proximos_partidos_invitado/', proximos_partidos_invitado, name='proximos_partidos_invitado'),
    path('api/invitaciones/<str:token>/aceptar/', AceptarInvitacionView.as_view(), name='aceptar-invitacion'),
    path('api/invitaciones/<str:token>/rechazar/', RechazarInvitacionView.as_view(), name='rechazar-invitacion'),
    path('api/horarios-ocupados/', get_ocupados, name='horarios-ocupados'),
    path('api/viviendas_por_codigo/', viviendas_por_codigo, name='viviendas_por_codigo'),
    path('api/password_reset/', include('django_rest_passwordreset.urls', namespace='password_reset')),
]

