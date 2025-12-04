from django.db import models
from django.contrib.auth.models import User, Group
from decimal import Decimal
from django.core.validators import MinValueValidator

# Create your models here.

class Producto(models.Model):

    id = models.BigAutoField(primary_key=True)

    nombre = models.CharField(
        max_length = 100
    )
    
    descripcion = models.TextField(
        blank = True,
        null = True
    )

    precio = models.DecimalField(
        max_digits = 10,
        decimal_places = 2
    ) 

    stock = models.IntegerField(
        default = 0
    )
    
    categoria = models.CharField(
        max_length = 50, 
        blank = True
    )
    
    imagen = models.ImageField(
        upload_to = 'productos/',
        null = True,
        blank = True
    )

    def __str__(self):
        return self.nombre

class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PREPARACION', 'En preparación'),
        ('LISTO', 'Listo para despacho'),
        ('ENVIADO', 'Enviado'),
        ('CANCELADO', 'Cancelado'),
    ]

    id = models.BigAutoField(
        primary_key = True
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete = models.SET_NULL,
        null = True,
        blank = True
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add = True
    )
    estado = models.CharField(
        max_length = 30,
        choices = ESTADO_CHOICES,
        default = 'PENDIENTE'
    )
    tiempo_despacho = models.DateTimeField(
        null = True,
        blank = True,
        help_text = "Fecha/hora programada de despacho"
    )
    almacenamiento_especial = models.BooleanField(
        default = False
    )
    observaciones = models.TextField(
        blank = True,
        null = True
    )
    # si ya tenías detalles de pedido con FK a Pedido, mantenlos
    # Relation to notifications (reverse relation provided by Notificacion.pedido)

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente or 'Cliente desconocido'} - {self.estado}"

class DetallePedido(models.Model):
    id = models.BigAutoField(primary_key=True)

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio unitario registrado al momento del pedido"
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Detalle de pedido"
        verbose_name_plural = "Detalles de pedido"
        unique_together = ('pedido', 'producto')
        ordering = ['-creado']

    def __str__(self):
        return f"Pedido #{self.pedido_id} - {self.producto.nombre} x{self.cantidad}"

    def save(self, *args, **kwargs):
        # Si no se pasó precio_unitario, tomar el precio actual del producto
        if self.precio_unitario in [None, ""]:
            self.precio_unitario = getattr(self.producto, 'precio', Decimal('0.00'))

        # asegurar Decimal para la multiplicación
        precio = Decimal(self.precio_unitario)
        qty = Decimal(self.cantidad)
        self.subtotal = (precio * qty).quantize(Decimal('0.01'))

        super().save(*args, **kwargs)

    @property
    def to_dict(self):
        """Útil para serializar rápido en vistas sin serializer."""
        return {
            "id": self.id,
            "pedido_id": self.pedido_id,
            "producto_id": self.producto_id,
            "producto_nombre": self.producto.nombre if self.producto_id else None,
            "cantidad": self.cantidad,
            "precio_unitario": float(self.precio_unitario),
            "subtotal": float(self.subtotal),
            "creado": self.creado,
        }

class Notificacion(models.Model):

    TIPO_CHOICES = [
        ('FALTA_PRODUCTO', 'Falta de producto'),
        ('CAMBIO_PEDIDO', 'Cambio pedido'),
        ('INFO_GENERAL', 'Información general'),
    ]
    RESPUESTA_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ACEPTADO', 'Aceptado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    id = models.BigAutoField(
        primary_key = True
    )
    pedido = models.ForeignKey(
        Pedido, 
        on_delete = models.CASCADE,
        related_name = 'notificaciones'
    )
    remitente = models.ForeignKey(
        User,
        on_delete = models.SET_NULL,
        null = True,
        related_name = 'notificaciones_enviadas'
    )
    destinatario = models.ForeignKey(
        User,
        on_delete = models.SET_NULL,
        null = True,
        blank = True,
        related_name = 'notificaciones_recibidas'
    )
    tipo = models.CharField(
        max_length = 30,
        choices = TIPO_CHOICES,
        default = 'INFO_GENERAL'
    )
    mensaje = models.TextField(
        max_length = 1000
    )
    fecha_envio = models.DateTimeField(
        auto_now_add = True
    )
    leida = models.BooleanField(
        default = False
    )
    estado_respuesta = models.CharField(
        max_length = 20,
        choices = RESPUESTA_CHOICES,
        default = 'PENDIENTE'
    )
    respuesta_texto = models.TextField(
        blank = True, null = True
    )
    fecha_respuesta = models.DateTimeField(
        null = True,
        blank = True
    )

    def __str__(self):
        return f"Notificación #{self.id} ({self.tipo}) -> Pedido {self.pedido_id}"

class Cliente(models.Model):
    
    user = models.OneToOneField(
        User,
        on_delete = models.CASCADE,
        null = True,
        blank = True
    )

    nombre = models.CharField(
        max_length = 100
    )

    apellido = models.CharField(
        max_length = 100
    )

    email = models.EmailField(
        unique = True
    )

    rut = models.CharField(
        max_length=12,
        null=False,
        blank=False,
        unique=True
    )


    telefono = models.CharField(
        max_length = 15,
        blank = True
    )

    direccion = models.CharField(
        max_length = 255,
        blank = True
    )

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

