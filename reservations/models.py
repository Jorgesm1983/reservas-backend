from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import secrets


class Community(models.Model):
    id = models.BigAutoField(primary_key=True)  # <--- Asegura que es bigint(20)
    name = models.CharField("Nombre de la comunidad", max_length=100)
    direccion = models.CharField("Dirección", max_length=255, blank=True, null=True)  # <-- Añade esto
    code = models.CharField(max_length=20, unique=True, null=False, blank=False, help_text="Código de registro de la comunidad")
    reserva_hora_apertura_pasado = models.TimeField(default="08:00", help_text="Hora apertura reservas para pasado mañana")
    reserva_max_dias = models.PositiveIntegerField(default=2, help_text="Máximo días vista (0=hoy, 1=mañana, 2=pasado mañana)")
    # Puedes añadir más campos si en el futuro necesitas reglas distintas
    # # Otros campos comunes a todas las comunidades (ej: contacto, logo, etc.)

    def __str__(self):
        return self.name
    
class Vivienda(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='viviendas', null=True, blank=True)

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
    nombre = models.CharField(_('nombre'), max_length=150)
    apellido = models.CharField(_('apellido'), max_length=150, blank=True)
    email = models.EmailField(_('email'), unique=True)
    vivienda = models.ForeignKey(Vivienda, on_delete=models.SET_NULL, null=True, blank=True)
    community = models.ForeignKey(Community, on_delete=models.SET_NULL, null=True, blank=True)  # Añadido
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



class Court(models.Model):
    name = models.CharField(max_length=100, unique=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, null = True, default= 1)  # Relación con comunidad
    # Opcional: sobreescribir la política por pista
    reserva_hora_apertura_pasado = models.TimeField(null=True, blank=True)
    reserva_max_dias = models.PositiveIntegerField(null=True, blank=True)
    # ... otros campos (ej: tipo de superficie, capacidad)

    def __str__(self):
        return f"{self.name} - {self.community}"
    class Meta:
        verbose_name_plural = "Pistas"

class TimeSlot(models.Model):
    court = models.ForeignKey('Court', on_delete=models.CASCADE, related_name="timeslots", null=False)
    slot = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('court', 'start_time', 'end_time')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.court.name} - {self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"

class Reservation(models.Model):  
    ESTADOS = (
        ('activa', 'Activa'),
        ('cancelada', 'Cancelada'),
    )
    
    user = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='reservations')  # Corregido
    court = models.ForeignKey(Court, on_delete=models.CASCADE)
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activa')  # ← NUEVO CAMPO

    class Meta:
        verbose_name_plural = "Reservas"
        constraints = [
            models.UniqueConstraint(
                fields=['court', 'date', 'timeslot'],
                name='unique_reservation_per_court_timeslot_date'
            )
        ]

    def __str__(self):
        return f"{self.user.nombre} - {self.court.name} - {self.date} {self.timeslot}"

    def can_be_cancelled_by(self, user):
        return self.user == user or user.is_staff
    
    def unique_error_message(self, model_class, unique_check):
        if model_class == type(self) and unique_check == ('court', 'timeslot', 'date'):
            return "Este horario ya está reservado"
        return super().unique_error_message(model_class, unique_check)

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
        ordering = ['-fecha_invitacion', '-id']  # <-- añade esto

    def generar_token(self):
        self.token = secrets.token_urlsafe(50)
        self.save()
        
    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(50)
        super().save(*args, **kwargs)
        
class InvitadoExterno(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='invitados_externos')
    email = models.EmailField()
    nombre = models.CharField(max_length=255)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'email')
        



class ReservationCancelada(models.Model):
    user = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, related_name='reservas_canceladas')
    court = models.ForeignKey('Court', on_delete=models.SET_NULL, null=True)
    timeslot = models.ForeignKey('TimeSlot', on_delete=models.SET_NULL, null=True)
    date = models.DateField()
    created_at = models.DateTimeField()  # Fecha de creación de la reserva original
    cancelada_at = models.DateTimeField(default=timezone.now)  # Fecha y hora de cancelación

    def __str__(self):
        return f"Reserva cancelada de {self.user} el {self.date} ({self.court})"
    
    class Meta:
        verbose_name_plural = "Reservas Canceladas"
