"""
URL configuration for vive_sano project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static

from modelos import views as modelos_vw
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", modelos_vw.inicio, name="inicio"),
    path("iniciar_sesion/", modelos_vw.registro, name="iniciar_sesion"),
    path("logout/", modelos_vw.cerrar_sesion, name="logout"),
    path("logistica/pedido/", modelos_vw.ver_pedidos, name="ver_pedidos"),
    path('logistica/pedido/<int:pedido_id>/preparar/', modelos_vw.preparar_pedido, name='preparar_pedido'),
    path('logistica/pedido/<int:pedido_id>/', modelos_vw.detalle_pedido_logistica, name='detalle_pedido_logistica'),
    path('logistica/pedido/<int:pedido_id>/notificar/', modelos_vw.enviar_notificacion, name='enviar_notificacion'),
    path("mis-pedidos/<int:pedido_id>/mensajes/responder/", modelos_vw.responder_mensaje_cliente, name="responder_mensaje_cliente"),
    path('atencion/notificaciones/', modelos_vw.lista_notificaciones, name='lista_notificaciones'),
    path("atencion/pedido/<int:pedido_id>/notificar-cliente/", modelos_vw.enviar_notificacion_cliente, name="notificar_cliente"),
    path('atencion/notificacion/<int:notificacion_id>/responder/', modelos_vw.responder_notificacion, name='responder_notificacion'),
    path("mis-pedidos/", modelos_vw.ver_pedidos_cliente, name="mis_pedidos"),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)