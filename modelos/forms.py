from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Pedido, Notificacion, Producto
from django.forms import ModelForm

from django import forms

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

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
        label="Nombre"
    )

    last_name = forms.CharField(
        max_length=100,
        required=True,
        label="Apellido"
    )

    email = forms.EmailField(
        required=True,
        label="Correo electrónico"
    )

    telefono = forms.CharField(
        max_length=15,
        required=False,
        label="Teléfono"
    )

    direccion = forms.CharField(
        max_length=255,
        required=False,
        label="Dirección"
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
    pedido_id = forms.IntegerField(widget=forms.HiddenInput)
    tiempo_despacho = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    almacenamiento_especial = forms.BooleanField(required=False)
    estado = forms.ChoiceField(choices=Pedido.ESTADO_CHOICES)
    observaciones = forms.CharField(widget=forms.Textarea, required=False)
    # Selección de productos (id: cantidad) — se puede mejorar con formsets
    productos = forms.CharField(required=False, help_text="JSON: [{producto_id:1, cantidad:2}, ...]")

class FiltrarPedidosForm(forms.Form):
    estado = forms.ChoiceField(choices=ESTADO_CHOICES)

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
