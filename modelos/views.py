from django.shortcuts import render, get_object_or_404, redirect
from django.forms.models import model_to_dict
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .forms import PrepararPedidoForm, NotificacionForm, FiltrarPedidosForm, NotificacionForm_Cliente, ESTADO_CHOICES
from django.db.models import Q


from .models import Producto, Pedido, DetallePedido, Notificacion
from .forms import CustomUserCreationForm
import json

# Create your views here.

def json_mensaje_retorno(codigo: int, mensaje: str) -> dict:

    formato_retorno = {
        "codigo": codigo,
        "mensaje": mensaje
    }

    return formato_retorno

def es_admin_logistica(user):
    return user.groups.filter(name="logistica").exists()

def is_logistica(user):
    return user.groups.filter(name='Logistica').exists() or user.is_staff

def is_atencion(user):
    return user.groups.filter(name='AtencionCliente').exists() or user.is_staff


def inicio(request):
    
    if request.method == "GET":
        try:
            productos = {
                "productos": Producto.objects.all()
            }

        except Exception as err:

            error_mensaje = json_mensaje_retorno(500, err)
            return render(request, "error.html", error_mensaje)
        
    if request.method == "POST":
        
        try:
            formulario_ = request.POST
            
            if "accion" not in formulario_:

                error_mensaje = json_mensaje_retorno(400, "Estas enviando un formulario sin todos los datos necesarios para enviar.")
                return render(request, "error.html", error_mensaje)

            if formulario_["accion"] == "ver_carrito":
                
                if "carrito" not in formulario_:

                    error_mensaje = json_mensaje_retorno(400, "Estas enviando un formulario incompleto.")
                    return render(request, "error.html", error_mensaje)
                
                try:
                    # Se obtiene unicamente el carrito del formulario
                    carrito_get = json.loads(formulario_["carrito"])
                except:
                    error_mensaje = json_mensaje_retorno(500, "El formato del json enviado no es valido.")
                    return render(request, "error.html", error_mensaje)                     

                carrito = []
                total_productos = 0
                total = 0

                for producto_ in carrito_get:
                    
                    # Se obtiene la informacion del modelo por id
                    resultado = get_object_or_404(Producto, pk=producto_["id"])
                    resultado_dict = model_to_dict(resultado)

                    # Se le agrega la cantidad enviada desde el formulario de inicio
                    resultado_dict["cantidad"] = producto_["cantidad"]

                    # Calcula el total y lo suma
                    total += resultado_dict["precio"] * producto_["cantidad"]
                    total_productos += producto_["cantidad"]
                    carrito.append(resultado_dict)

                # Formateando salida xd
                carrito_items = {
                    "carrito_items": carrito,
                    "total_productos": total_productos,
                    "total_precio": total
                }
                
                # Salida
                return render(request, "carrito.html", carrito_items)

            if formulario_["accion"] == "enviar_pedido":

                if not request.user.is_authenticated:
                    return render(request, "error.html", json_mensaje_retorno(401, "Debes iniciar sesión para enviar un pedido."))

                if "carrito" not in formulario_:
                    return render(request, "error.html", json_mensaje_retorno(400, "No enviaste el carrito mi chico."))

                try:
                    carrito_get = json.loads(formulario_["carrito"])
                except:
                    return render(request, "error.html", json_mensaje_retorno(500, "El carrito enviado no es JSON válido."))

                if len(carrito_get) == 0:
                    return render(request, "error.html", json_mensaje_retorno(400, "No puedes enviar un pedido vacío."))

                # Buscar cliente
                cliente = getattr(request.user, "cliente", None)
                if cliente is None:
                    return render(request, "error.html", json_mensaje_retorno(400, "Tu usuario no tiene un cliente asociado."))

                with transaction.atomic():

                    # Crear el pedido correctamente
                    pedido = Pedido.objects.create(
                        cliente=cliente,          # ✔ Tu modelo usa cliente, no usuario
                        estado="PENDIENTE"        # ✔ coincide con tu modelo
                        # fecha_creacion se llena sola
                    )

                    total = 0

                    # Crear los detalles del pedido
                    for item in carrito_get:
                        producto = get_object_or_404(Producto, pk=item["id"])
                        cantidad = int(item["cantidad"])

                        if cantidad <= 0:
                            continue

                        total += producto.precio * cantidad

                        DetallePedido.objects.create(
                            pedido=pedido,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=producto.precio
                        )

                    # (Opcional) Si tu modelo tiene total, puedes añadirlo aquí
                    # pedido.total = total
                    # pedido.save()

                return render(request, "pedido_creado.html", {
                    "pedido": pedido,
                    "total": total,
                })


        except Exception as err:
            
            json_error = json_mensaje_retorno(500, err)
            return render(request, "error.html", json_error)

    return render(request, "inicio.html", productos)

@login_required
def ver_pedidos_cliente(request):
    # Verificar si el usuario tiene un cliente asociado
    cliente = getattr(request.user, "cliente", None)
    if cliente is None:
        return render(request, "inicio.html", json_mensaje_retorno(400, "Tu usuario no tiene un cliente asociado."))

    # Obtener pedidos del cliente (ordenados del más reciente al más antiguo)
    pedidos = Pedido.objects.filter(cliente=cliente).order_by("-fecha_creacion")

    # Preparar la estructura para mostrar cada pedido con sus detalles
    pedidos_con_detalles = []
    for p in pedidos:
        detalles = p.detallepedido_set.select_related("producto").all()
        pedidos_con_detalles.append({
            "pedido": p,
            "detalles": detalles
        })

    return render(request, "mis_pedidos.html", {
        "pedidos": pedidos_con_detalles
    })

@login_required
def obtener_notificaciones(request):
    
    pass


@login_required
@user_passes_test(is_logistica)
def preparar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    if request.method == 'POST':
        form = PrepararPedidoForm(request.POST)
        if form.is_valid():
            tiempo = form.cleaned_data.get('tiempo_despacho')
            almacenamiento = form.cleaned_data.get('almacenamiento_especial')
            estado = form.cleaned_data.get('estado')
            observaciones = form.cleaned_data.get('observaciones')
            productos_json = form.cleaned_data.get('productos')

            # Actualizar pedido
            pedido.tiempo_despacho = tiempo
            pedido.almacenamiento_especial = almacenamiento
            pedido.estado = estado
            pedido.observaciones = observaciones
            pedido.save()

            # Procesar productos y disminuir stock
            if productos_json:
                try:
                    productos_list = json.loads(productos_json)
                except Exception:
                    productos_list = []
                with transaction.atomic():
                    for item in productos_list:
                        pid = item.get('producto_id')
                        qty = int(item.get('cantidad', 0))
                        if qty <= 0:
                            continue
                        producto = Producto.objects.select_for_update().get(pk=pid)
                        if producto.stock < qty:
                            # Crear notificación de falta de producto
                            Notificacion.objects.create(
                                pedido=pedido,
                                remitente=request.user,
                                tipo='FALTA_PRODUCTO',
                                mensaje=f"Falta stock para producto {producto.nombre}. Se necesita {qty}, hay {producto.stock}.",
                            )
                            messages.warning(request, f"Stock insuficiente para {producto.nombre}. Notificación enviada.")
                        else:
                            # ajustar stock
                            producto.stock -= qty
                            producto.save()
                            # Crear o actualizar DetallePedido
                            detalle, created = DetallePedido.objects.get_or_create(pedido=pedido, producto=producto, defaults={'cantidad': qty})
                            if not created:
                                detalle.cantidad = detalle.cantidad + qty
                                detalle.save()
                    messages.success(request, "Pedido actualizado correctamente.")

            return redirect('detalle_pedido_logistica', pedido_id=pedido.id)

    else:
        form = PrepararPedidoForm(initial={'pedido_id': pedido.id, 'estado': pedido.estado, 'almacenamiento_especial': pedido.almacenamiento_especial})

    # preparar lista de productos (para revisar stock)
    productos = Producto.objects.all()
    detalles = pedido.detallepedido_set.all() if hasattr(pedido, 'detallepedido_set') else []

    return render(request, 'logistica/preparar_pedido.html', {
        'pedido': pedido,
        'form': form,
        'productos': productos,
        'detalles': detalles,
    })

@login_required
@user_passes_test(is_logistica)
def detalle_pedido_logistica(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    detalles = pedido.detallepedido_set.select_related('producto').all()
    return render(request, 'logistica/detalle_pedido_logistica.html', {'pedido': pedido, 'detalles': detalles})

@login_required
@user_passes_test(is_logistica)
def enviar_notificacion(request, pedido_id):

    notis = list(Notificacion.objects.filter(pedido_id=pedido_id).order_by('-fecha_envio'))

    pedido = get_object_or_404(Pedido, pk=pedido_id)
    if request.method == 'POST':
        form = NotificacionForm(request.POST)
        if form.is_valid():
            noti = form.save(commit=False)
            noti.pedido = pedido
            noti.remitente = request.user
            noti.save()
            messages.success(request, "Notificación enviada.")
            return redirect('preparar_pedido', pedido_id=pedido.id)
    else:
        form = NotificacionForm()
    return render(request, 'logistica/enviar_notificacion.html', {'form': form, 'pedido': pedido, "notificaciones": notis})

@login_required
@user_passes_test(is_logistica)
def ver_pedidos(request):

    form = FiltrarPedidosForm()

    if request.method == "POST":
        form_filter = request.POST

        if "estado" not in form_filter:
            return render(request, "logistica/pedidos_logistica.html", json_mensaje_retorno(402, "Estas enviando un formulario incompleto."))
        
        if form_filter["estado"][0] not in str(ESTADO_CHOICES):
            return render(request, "logistica/pedidos_logistica.html", json_mensaje_retorno(402, "Formulario corrupto."))

        resultado_ = list(Pedido.objects.filter(estado = form_filter["estado"]))

        if not resultado_:
            return render(request, "logistica/pedidos_logistica.html", json_mensaje_retorno(404, f"No existe pedido en estado {form_filter['estado'].lower()}."))

        return render(request, "logistica/pedidos_logistica.html", {
            "pedidos": resultado_, "form": form 
        })

    try:
        resultado_ = list(Pedido.objects.filter(estado = "PENDIENTE"))

    except:
        return render(request, "logistica/pedidos_logistica.html", json_mensaje_retorno(500, "Ocurrio un error, no se logro obtener los pedidos pendientes."))
    
    if not resultado_:
        return render(request, "logistica/pedidos_logistica.html", json_mensaje_retorno(404, "No se logro encontrar ningun pedido pendiente."))
    
    return render(request, "logistica/pedidos_logistica.html", {
        "pedidos": resultado_, "form": form 
    })

@login_required
@user_passes_test(is_atencion)
def lista_notificaciones(request):
    # usuario de atención ve notificaciones dirigidas a su grupo o a él directamente
    notis = Notificacion.objects.filter(destinatario=request.user).order_by('-fecha_envio')
    # Si quieres que Atención vea tambien las notificaciones sin destinatario:
    # notis = Notificacion.objects.filter(models.Q(destinatario=request.user) | models.Q(destinatario__isnull=True)).order_by('-fecha_envio')
    return render(request, 'servicio_cliente/notificaciones.html', {'notificaciones': notis})

@login_required
@user_passes_test(is_atencion)
def responder_notificacion(request, notificacion_id):
    noti = get_object_or_404(Notificacion, pk=notificacion_id)
    if request.method == 'POST':
        respuesta = request.POST.get('respuesta')
        texto = request.POST.get('texto', '')
        if respuesta in ['ACEPTADO', 'RECHAZADO']:
            noti.estado_respuesta = respuesta
            noti.respuesta_texto = texto
            noti.fecha_respuesta = timezone.now()
            noti.leida = True
            noti.save()
            # opcional: crear una notificacion de vuelta a quien corresponda (remitente o grupo logistica)
            Notificacion.objects.create(
                pedido=noti.pedido,
                remitente=request.user,
                destinatario=noti.remitente,
                tipo='INFO_GENERAL',
                mensaje=f"Respuesta a notificación #{noti.id}: {respuesta}. {texto}",
            )
            messages.success(request, "Respuesta enviada.")
            return redirect('lista_notificaciones')
        else:
            messages.error(request, "Respuesta inválida.")
    return render(request, 'servicio_cliente/responder_notificacion.html', {'notificacion': noti})

@login_required
@user_passes_test(is_atencion)
def enviar_notificacion_cliente(request, pedido_id):

    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # Historial de notificaciones relacionadas al pedido
    notificaciones = Notificacion.objects.filter(
        pedido=pedido
    ).order_by('-fecha_envio')

    detalle = DetallePedido.objects.filter(
        pedido=pedido.id
    )

    if request.method == "POST":
        form = NotificacionForm_Cliente(request.POST)

        if form.is_valid():
            noti = form.save(commit=False)
            noti.pedido = pedido
            noti.remitente = request.user    # logistica
            noti.destinatario = pedido.cliente.user  # envío DIRECTO al cliente
            noti.tipo = noti.tipo or "INFO_GENERAL"  # por si viene vacío
            noti.save()

            messages.success(request, "Notificación enviada al cliente.")
            return redirect("notificar_cliente", pedido_id=pedido.id)

        else:
            messages.error(request, "El formulario contiene errores.")

    else:
        form = NotificacionForm_Cliente()

    return render(request, "servicio_cliente/enviar_notificacion_cliente.html", {
        "pedido": pedido,
        "form": form,
        "notificaciones": notificaciones,
        "detalle": detalle
    })

@login_required
def responder_mensaje_cliente(request, pedido_id):

    # El cliente debe ser dueño del pedido
    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        cliente=request.user.cliente
    )


    mensajes = list(
        Notificacion.objects.filter(
            pedido_id=pedido_id
        ).filter(
            Q(destinatario=request.user) | Q(remitente=request.user)
        ).order_by("-fecha_envio")
    )

    if request.method == "POST":
        mensaje = request.POST.get("mensaje", "").strip()

        if not mensaje:
            messages.error(request, "El mensaje no puede estar vacío.")
            return redirect("responder_mensaje_cliente", pedido_id=pedido.id)
        
        if not mensajes:
            return render(request, "cliente/responder_mensaje_cliente.html", json_mensaje_retorno(404, "No tienes notificaciones asociadas al peddido."))

        destinatario = 0
        for mensaje_iter in mensajes:
            if mensaje_iter.remitente != request.user.id:
                destinatario = mensaje_iter.remitente
                break
        
        if destinatario == 0:
            return render(request, "cliente/responder_mensaje_cliente.html", json_mensaje_retorno(404, "No encontramos el id del remitente."))

        # Crear la respuesta como notificación
        Notificacion.objects.create(
            pedido=pedido,
            remitente=request.user,
            destinatario=destinatario or None,  # operador logístico si existe
            mensaje=mensaje,
            tipo="RESPUESTA_CLIENTE"
        )

        messages.success(request, "Tu mensaje fue enviado correctamente.")
        return redirect("responder_mensaje_cliente", pedido_id=pedido.id)

    return render(request, "cliente/responder_mensaje_cliente.html", {"pedido_id": pedido.id, "mensajes": mensajes})

def registro(request):

    if request.method == "GET":
        return render(request, "registro.html", {"form": CustomUserCreationForm()})
    
    if request.method == "POST":
        
        formulario_enviado = request.POST

        if "accion" not in formulario_enviado:
            return render(request, "error.html", json_mensaje_retorno(402, "Estas enviando un formulario incompleto o corrupto."))
        
        if formulario_enviado["accion"] == "crear_cuenta":

            # Se envia el formulario llenado para verificar si es valido
            formulario = CustomUserCreationForm(formulario_enviado)
            if not formulario.is_valid():
                return render(request, "registro.html", json_mensaje_retorno(402, "Estas enviando un formulario corrupto o incompleto."))

            # Se guarda la cuenta en la base de datos
            usuario_creado = formulario.save()

            # Crear su cliente asociado automacit
            from .models import Cliente

            # Evitar duplicado por si existiera
            if not hasattr(usuario_creado, "cliente"):
                Cliente.objects.create(
                    user=usuario_creado,
                    nombre=formulario.cleaned_data["first_name"],
                    apellido=formulario.cleaned_data["last_name"],
                    email=formulario.cleaned_data["email"],
                    telefono=formulario.cleaned_data.get("telefono", ""),
                    direccion=formulario.cleaned_data.get("direccion", "")
                )


            return render(request, "registro.html", json_mensaje_retorno(200, "Cuenta creada exitosamente."))


        if formulario_enviado["accion"] == "iniciar_sesion":

            # si las claves usuario y contraseña (del diccionario) no existe o faltan en el
            if all(x not in formulario_enviado for x in ["usuario", "contrasena"]):    
                error_mensaje = json_mensaje_retorno(402, "Estas enviando un formulario corrupto o incompleto.")
                return render(request, "error.html", error_mensaje)

            usuario = formulario_enviado["usuario"]
            contrasena = formulario_enviado["contrasena"]

            # Se utiliza la funcion de django para verificar que el usuario y contraseña exista en la bdd
            user = authenticate(request, username = usuario, password = contrasena)

            # Si no existe usuario o no se devuelve nada se envia un mensaje diciendo o preguntando sobre la contraseña.
            if not user:
                error_mensaje = json_mensaje_retorno(404, "Estas seguro que te sabes tu contraseña? Porque no te pudimos logear.")
                return render(request, "registro.html", error_mensaje)

            login(request, user)

            # Iniciando sesion se redirige al carrito para realizar el pedido
            return redirect(inicio)

def cerrar_sesion(request):
    logout(request)
    return redirect("iniciar_sesion")
