from django.contrib import admin
from .models import Producto, Cliente, Pedido, Notificacion

# Register your models here.
admin.site.register(Producto)
admin.site.register(Cliente)

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'pedido', 'remitente', 'destinatario', 'fecha_envio', 'estado_respuesta', 'leida')
    list_filter = ('tipo', 'estado_respuesta', 'leida')
    search_fields = ('mensaje',)

# si ya registraste Pedido y Producto, puedes personalizar su admin:
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'tiempo_despacho')
    list_filter = ('estado',)
    search_fields = ('cliente__nombre',)
