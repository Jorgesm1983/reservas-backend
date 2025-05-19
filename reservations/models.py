from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _
import secrets


class Vivienda(models.Model):
    nombre = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.nombre

class UsuarioManager(BaseUserManager):
    def create_user(self, email, nombre, password=None, apellido="", vivienda=None):
        if not email:
            raise ValueError('El usuario debe tener un email')
        user = self.model(
            email=self.normalize_email(email),
            nombre=nombre,
            apellido=apellido,
            vivienda=vivienda
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nombre, password=None, apellido="", vivienda=None):
        user = self.create_user(
            email=email,
            nombre=nombre,
            password=password,
            apellido=apellido,
            vivienda=vivienda
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class Usuario(AbstractBaseUser, PermissionsMixin):
    nombre = models.CharField(_('nombre'), max_length=150, unique=True)
    apellido = models.CharField(_('apellido'), max_length=150, blank=True)
    email = models.EmailField(_('email'), unique=True)
    vivienda = models.ForeignKey(Vivienda, on_delete=models.SET_NULL, null=True, blank=True)
    is_staff = models.BooleanField(_('staff'), default=False)
    is_active = models.BooleanField(_('activo'), default=True)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'  # Ahora el nombre es el campo principal
    REQUIRED_FIELDS = ['nombre']  # Campos requeridos para createsuperuser

    objects = UsuarioManager()

    class Meta:
        verbose_name = _('usuario')
        verbose_name_plural = _('usuarios')
        
    def get_full_name(self):
        """
        Devuelve el nombre completo del usuario.
        Si no tiene nombre/apellido, usa el username.
        """
        if self.nombre and self.apellido:
            return f"{self.nombre} {self.apellido}"
        else:
            return self.email  # o self.email según prefieras

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()

class Community(models.Model):
    name = models.CharField("Nombre de la comunidad", max_length=100)
    # Otros campos comunes a todas las comunidades (ej: contacto, logo, etc.)

    def __str__(self):
        return self.name

class Court(models.Model):
    name = models.CharField(max_length=100, unique=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, null = True, default= 1)  # Relación con comunidad
    # ... otros campos (ej: tipo de superficie, capacidad)

    def __str__(self):
        return f"{self.name} - {self.community}"
    class Meta:
        verbose_name_plural = "Pistas"

class TimeSlot(models.Model):
    slot = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('start_time', 'end_time')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

class Reservation(models.Model):
    user = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='reservations')  # Corregido
    court = models.ForeignKey(Court, on_delete=models.CASCADE)
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Reservas"
        constraints = [
            models.UniqueConstraint(
                fields=['court', 'timeslot', 'date'],
                name='unique_reservation'
            )
        ]

    def __str__(self):
        return f"{self.user.nombre} - {self.court.name} - {self.date} {self.timeslot}"

    def can_be_cancelled_by(self, user):
        return self.user == user or user.is_staff

class ReservationInvitation(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada')
    )
    
    reserva = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='invitaciones')
    invitado = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    token = models.CharField(max_length=100, unique=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_invitacion = models.DateTimeField(auto_now_add=True)
    nombre_invitado = models.CharField("Nombre del invitado", max_length=255, blank=True, null=True)

    class Meta:
        unique_together = [['reserva', 'email']]
        verbose_name_plural = "Invitaciones"

    def generar_token(self):
        self.token = secrets.token_urlsafe(50)
        self.save()
        
class InvitadoExterno(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='invitados_externos')
    email = models.EmailField()
    nombre = models.CharField(max_length=255)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'email')