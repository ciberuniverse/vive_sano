from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Pedido, Notificacion, Producto
from django.forms import ModelForm

from django import forms

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

# Validador para nombres y apellidos (solo letras y espacios)
name_validator = RegexValidator(
    regex=r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$',
    message="Solo se permiten letras y espacios."
)

# Validador para teléfono (solo números, opcionalmente con + al inicio)
phone_validator = RegexValidator(
    regex=r'^\+?\d{7,15}$',
    message="Ingrese un número de teléfono válido (solo dígitos, opcional +)."
)

# Validador para dirección (letras, números, espacios y algunos signos permitidos)
address_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.,#-]+$',
    message="La dirección contiene caracteres no permitidos."
)

email_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    message="Ingrese un correo electrónico válido sin caracteres especiales no permitidos."
)

rut_format_validator = RegexValidator(
    regex=r'^\d{1,2}\d{3}\d{3}-[\dkK]{1}$',
    message="Ingrese un RUT válido con guion y dígito verificador (ej: 12345678-9 o 12345678-K)."
)

# Función para validar el dígito verificador del RUT
def validar_rut(value):

    try:
        rut, dv = value.split('-')
        rut = rut.replace(".", "")
        suma = 0
        multiplo = 2

        for digit in reversed(rut):
            suma += int(digit) * multiplo
            multiplo += 1
            if multiplo > 7:
                multiplo = 2

        resto = suma % 11
        dv_calculado = 11 - resto
        if dv_calculado == 11:
            dv_calculado = '0'
        elif dv_calculado == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(dv_calculado)

        if dv.upper() != dv_calculado:
            raise ValidationError("El dígito verificador del RUT no es válido.")

    except:
        pass

ESTADO_CHOICES = [
    ('PENDIENTE', 'Pendiente'),
    ('EN_PREPARACION', 'En preparación'),
    ('LISTO', 'Listo para despacho'),
    ('ENVIADO', 'Enviado'),
    ('CANCELADO', 'Cancelado'),
]

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=100,
        required=True,
        label="Nombre",
        validators=[name_validator]
    )

    last_name = forms.CharField(
        max_length=100,
        required=True,
        label="Apellido",
        validators=[name_validator]
    )

    rut = forms.CharField(
        max_length=12,
        required=True,
        label="RUT",
        validators=[rut_format_validator, validar_rut]
    )

    email = forms.EmailField(
        required=True,
        max_length=60,
        label="Correo electrónico",
        validators=[email_validator]
    )

    telefono = forms.CharField(
        max_length=15,
        required=True,
        label="Teléfono",
        validators=[phone_validator]
    )

    direccion = forms.CharField(
        max_length=255,
        required=True,
        label="Dirección",
        validators=[address_validator]
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "telefono",
            "direccion",
        )


class PrepararPedidoForm(forms.Form):
    
    pedido_id = forms.IntegerField(
        widget = forms.HiddenInput
    )
    
    tiempo_despacho = forms.DateTimeField(
        required = False,
        widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    
    almacenamiento_especial = forms.BooleanField(
        required = False
    )
    
    estado = forms.ChoiceField(
        choices = Pedido.ESTADO_CHOICES
    )
    
    observaciones = forms.CharField(
        widget = forms.Textarea,
        required = False
    )

    # Selección de productos (id: cantidad) — se puede mejorar con formsets
    productos = forms.CharField(
        required = False,
        help_text = "JSON: [{producto_id:1, cantidad:2}, ...]"
    )

class FiltrarPedidosForm(forms.Form):
    
    estado = forms.ChoiceField(
        choices = ESTADO_CHOICES
    )

class NotificacionForm(forms.ModelForm):
    
    class Meta:
        model = Notificacion
        fields = ['tipo', 'mensaje', 'destinatario']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar destinatarios por grupo "AtencionCliente"
        self.fields['destinatario'].queryset = User.objects.filter(groups__name="AtencionCliente")

class NotificacionForm_Cliente(forms.ModelForm):
    
    class Meta:
        model = Notificacion
        fields = ['tipo', 'mensaje']
