from django.shortcuts import render, get_object_or_404, redirect
from django.forms.models import model_to_dict
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from .validator import validar_caracteres
from django.utils import timezone
from django.db import transaction
from .forms import PrepararPedidoForm, NotificacionForm, FiltrarPedidosForm, NotificacionForm_Cliente, ESTADO_CHOICES,  CustomUserCreationForm, FiltrarPedidosForm
from django.db.models import Q

# Trans bank
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType

from .models import Producto, Pedido, DetallePedido, Notificacion, Cliente
import json, time

# Create your views here.

chars_allowed = {
    "alph": "qwertyuiopasdfghjklñzxcvbnm",
    "numb": "1234567890",
    "spec": "_.@,"
}

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
            return render(request, "inicio.html", error_mensaje)
        
    if request.method == "POST":
        
        try:
            formulario_ = request.POST
            
            if "accion" not in formulario_:

                error_mensaje = json_mensaje_retorno(400, "Estas enviando un formulario sin todos los datos necesarios para enviar.")
                return render(request, "inicio.html", error_mensaje)

            if formulario_["accion"] == "ver_carrito":
                
                if "carrito" not in formulario_:

                    error_mensaje = json_mensaje_retorno(400, "Estas enviando un formulario incompleto.")
                    return render(request, "inicio.html", error_mensaje)
                
                try:
                    # Se obtiene unicamente el carrito del formulario
                    carrito_get = json.loads(formulario_["carrito"])
                except:
                    error_mensaje = json_mensaje_retorno(500, "El formato del json enviado no es valido.")
                    return render(request, "inicio.html", error_mensaje)                     

                carrito = []
                total_productos = 0
                total = 0

                for producto_ in carrito_get:
                    
                    # Se obtiene la informacion del modelo por id
                    resultado = get_object_or_404(Producto, pk=producto_["id"])
                    resultado_dict = model_to_dict(resultado)
                    print(producto_)
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
                    return render(request, "inicio.html", json_mensaje_retorno(401, "Debes iniciar sesión para enviar un pedido."))

                if "carrito" not in formulario_:
                    return render(request, "inicio.html", json_mensaje_retorno(400, "No enviaste el carrito mi chico."))

                try:
                    carrito_get = json.loads(formulario_["carrito"])
                    print(carrito_get)
                except:
                    return render(request, "inicio.html", json_mensaje_retorno(500, "El carrito enviado no es JSON válido."))

                if len(carrito_get) == 0:
                    return render(request, "inicio.html", json_mensaje_retorno(400, "No puedes enviar un pedido vacío."))

                # Buscar cliente
                cliente = getattr(request.user, "cliente", None)
                if cliente is None:
                    return render(request, "inicio.html", json_mensaje_retorno(400, "Tu usuario no tiene un cliente asociado."))


                sobrepasado_ = []
                productos_inv = Producto.objects.all()

                for producto in carrito_get:
                    
                    producto_bdd = productos_inv.get(id=producto['id'])
                    cantidad = producto_bdd.stock

                    if cantidad < producto['cantidad']:

                        sobre_ = int(producto['cantidad']) - int(cantidad) 
                        sobrepasado_.append(f"El stock de {producto_bdd.nombre} tiene {cantidad} y te pasas: {sobre_}.")

                if sobrepasado_:
                    sobrepasado_ = "\n".join(sobrepasado_)
                    return render(request, "inicio.html", json_mensaje_retorno(400, f"Estas llevando sobre el stock. {sobrepasado_}"))

                with transaction.atomic():

                    # Crear el pedido correctamente
                    pedido = Pedido.objects.create(
                        cliente=cliente,
                        estado="PENDIENTE"       
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

                    # pedido.total = total
                    # pedido.save()
                
                # Se obtiene el id del cliente
                session_id_token = request.session.get("_auth_user_id")
                # Se crea el tipo de transaccion
                tx = Transaction(WebpayOptions(
                    IntegrationCommerceCodes.WEBPAY_PLUS, 
                    IntegrationApiKeys.WEBPAY, 
                    IntegrationType.TEST
                ))

                # Se le asigna un identificador que el pedido tendra siempre dentro de webpay tanto para la session como para la orden
                buy_order = f"P-{pedido.id}-{session_id_token}-{int(time.time())}"
                session_id = f"S-{session_id_token}-{int(time.time())}"

                # La cantidad, url, y respuesta de la creacion de la orden.
                amount = int(total)
                return_url = request.build_absolute_uri('/webpay/retorno') 
                response = tx.create(buy_order, session_id, amount, return_url)


                print(response['url'] + '?token_ws=' + response['token'])
                return redirect(response['url'] + '?token_ws=' + response['token'])
                # Se redirige a la vista de comprobacion de pago en donde se procesara.
                return redirect("webpay_pago", response_token = response['token'])


        except Exception as err:
            
            json_error = json_mensaje_retorno(500, f"ERROR: Ocurrio un problema al procesar tu pedido: {err}")
            return render(
                request,
                "logistica/pedidos_logistica.html",
                json_error
            )
    
    return render(request, "inicio.html", productos)

@login_required
def ver_pedidos_cliente(request):
    # Verificar si el usuario tiene un cliente asociado
    cliente = getattr(request.user, "cliente", None)
    if cliente is None:
        return render(request, "inicio.html", json_mensaje_retorno(400, "Tu usuario no tiene un cliente asociado."))

    # Instanciar el formulario (POST o vacío)
    if request.method == "POST":
        form = FiltrarPedidosForm(request.POST)
    else:
        form = FiltrarPedidosForm()

    # Base queryset: solo pedidos del cliente, ordenados por fecha
    queryset = Pedido.objects.filter(cliente=cliente).order_by("-fecha_creacion")

    # Si es POST y el formulario es válido, aplicar filtros
    if request.method == "POST" and form.is_valid():
        filtros = form.cleaned_data
        estado = filtros.get("estado")
        fecha_desde = filtros.get("fecha_desde")

        if estado:
            queryset = queryset.filter(estado=estado)
        if fecha_desde:
            queryset = queryset.filter(fecha__gte=fecha_desde)
    elif request.method == "POST" and not form.is_valid():
        # Formulario inválido: no mostrar pedidos (comportamiento original)
        queryset = Pedido.objects.none()

    # Traer detalles y producto relacionados para evitar N+1
    queryset = queryset.prefetch_related("detallepedido_set__producto")

    # Preparar la estructura pedidos_con_detalles
    pedidos_con_detalles = []
    for p in queryset:
        detalles = p.detallepedido_set.all()  # ya prefetched
        pedidos_con_detalles.append({
            "pedido": p,
            "detalles": detalles
        })

    return render(request, "mis_pedidos.html", {
        "form": form,
        "pedidos": pedidos_con_detalles
    })

@login_required
@user_passes_test(is_logistica)
def preparar_pedido(request, pedido_id):

    pedido_str_id = str(pedido_id)
    if not pedido_str_id.isnumeric() or len(pedido_str_id) > 5:
        return render(request, "logistica/preparar_pedido.html", json_mensaje_retorno(402, "Estas inyectando parametros por el id."))
    

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

    pedido_str_id = str(pedido_id)
    if not pedido_str_id.isnumeric() or len(pedido_str_id) > 5:
        return render(request, "logistica/detalle_pedido_logistica.html", json_mensaje_retorno(402, "Estas inyectando parametros por el id."))
    

    pedido = get_object_or_404(Pedido, pk=pedido_id)
    detalles = pedido.detallepedido_set.select_related('producto').all()
    return render(request, 'logistica/detalle_pedido_logistica.html', {'pedido': pedido, 'detalles': detalles})

@login_required
@user_passes_test(is_logistica)
def enviar_notificacion(request, pedido_id):

    pedido_str_id = str(pedido_id)
    if not pedido_str_id.isnumeric() or len(pedido_str_id) > 5:
        return render(request, "logistica/enviar_notificacion.html", json_mensaje_retorno(402, "Estas inyectando parametros por el id."))
    
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

    pedido_str_id = str(notificacion_id)
    if not pedido_str_id.isnumeric() or len(pedido_str_id) > 5:
        return render(request, "servicio_cliente/responder_notificacion.html", json_mensaje_retorno(402, "Estas inyectando parametros por el id."))
    
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



    pedido_str_id = str(pedido_id)
    if not pedido_str_id.isnumeric() or len(pedido_str_id) > 5:
        return render(request, "servicio_cliente/enviar_notificacion_cliente.html", json_mensaje_retorno(402, "Estas inyectando parametros por el id."))
    

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
def webpay_redirect(request):
    return render(request, "cliente/obtener_url_pedido.html")

@login_required
def webpay(request):

    response_token = request.GET.get('token_ws') or request.POST.get('token_ws') or request.GET.get("TBK_TOKEN")
    if not response_token:
        return redirect('inicio', json_mensaje_retorno(402, "No se logro obtener ningun parametro de token."))

    # Estructura de respuesta por defecto
    retorno_mensaje = json_mensaje_retorno(500, "Ocurrió un error al procesar el pago.")

    ##### Se intenta obtener el TBK_token si existe se obtiene tambien el TBK_ORDEN_COMPRA
    if request.GET.get("TBK_TOKEN"):

        buy_order = str(request.GET.get('TBK_ORDEN_COMPRA'))
        pedido_id = buy_order.split('-')[1]

        if pedido_id:
            Pedido.objects.filter(id=pedido_id).delete()

        retorno_mensaje = json_mensaje_retorno(500, "Se anulo la compra del pedido.")
        return render(request, "inicio.html", retorno_mensaje)

    else: 
        pedido = None
        pedido_id = None

    try:
        # 1) Instanciar cliente Webpay
        tx = Transaction(WebpayOptions(
            IntegrationCommerceCodes.WEBPAY_PLUS,
            IntegrationApiKeys.WEBPAY,
            IntegrationType.TEST,
        ))

        # 2) Confirmar transacción con token
        response = tx.commit(response_token)

        # Validaciones básicas del response
        if not response or "buy_order" not in response:
            return render(request, "inicio.html", json_mensaje_retorno(400, "Respuesta inválida de Webpay (sin buy_order)."))

        buy_order = str(response['buy_order'])
        pedido_id = buy_order.split('-')[1]

        parts = buy_order.split("-")
        if len(parts) < 2 or not parts[1].isdigit():
            return render(request, "inicio.html", json_mensaje_retorno(400, "buy_order con formato inválido."))

        pedido_id = int(pedido_id)

        # 3) Obtener el pedido
        try:
            pedido = Pedido.objects.get(id=pedido_id)
        except Pedido.DoesNotExist:
            return render(request, "inicio.html", json_mensaje_retorno(404, "Pedido no encontrado."))

        # 4) Actualizar estado según response_code
        response_code = response.get("response_code")
        with transaction.atomic():
            if response_code == 0:
                pedido.estado = "PAGADO"
                pedido.save(update_fields=["estado"])
                retorno_mensaje = json_mensaje_retorno(200, "Pedido creado y pagado exitosamente.")
            else:
                pedido.estado = "CANCELADO"
                pedido.save(update_fields=["estado"])
                retorno_mensaje = json_mensaje_retorno(402, "Pedido rechazado o cancelado por Webpay.")


        return render(request, "pedido_creado.html", retorno_mensaje)

    except Exception as err:
        # Loguear el error con contexto útil
        print(f"[Webpay commit error] token={response_token} pedido_id={pedido_id} err={err}")

        print(pedido_id)
        if pedido_id:
            Pedido.objects.filter(id=pedido_id).delete()

        retorno_mensaje = json_mensaje_retorno(500, "Ocurrió un error al intentar procesar el pago.")

        return render(request, "inicio.html", retorno_mensaje)

    
    return render(request, "inicio.html", retorno_mensaje)

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
                return render(request, "registro.html", json_mensaje_retorno(402, f"Estas enviando un formulario corrupto o incompleto: {formulario.errors.as_text()}"))

            validar_formulario = {
                "username": [150, chars_allowed["alph"] + chars_allowed["numb"] + "@.+-_"],
                "password1": [30, chars_allowed["alph"] + chars_allowed["numb"] + "_"],
                "password2": [30, chars_allowed["alph"] + chars_allowed["numb"] + "_"],

                "first_name": [100, chars_allowed["alph"] + " "],
                "last_name": [100, chars_allowed["alph"] + " "],
                "rut": [12, chars_allowed["numb"] + "-k"],
                "email": [60, chars_allowed["alph"] + chars_allowed["numb"] + "@."],
                "telefono": [15, chars_allowed["numb"] + "+"],
                "direccion": [255, chars_allowed["alph"] + chars_allowed["numb"] + ",. "],
            }
            print("xd")

            resultado_valid = validar_caracteres(formulario_enviado, validar_formulario)
            if resultado_valid["codigo"] != 200:
                return render(request, "registro.html", resultado_valid)

            if Cliente.objects.filter(rut=formulario_enviado["rut"]).exists():
                return render(request, "registro.html", json_mensaje_retorno(402, f"Ya existe un usuario con ese RUT."))

            # Se guarda la cuenta en la base de datos
            usuario_creado = formulario.save()

            # Evitar duplicado por si existiera
            if not hasattr(usuario_creado, "cliente"):
                Cliente.objects.create(
                    user = usuario_creado,
                    nombre = formulario.cleaned_data["first_name"],
                    apellido = formulario.cleaned_data["last_name"],
                    email = formulario.cleaned_data["email"],
                    telefono = formulario.cleaned_data.get("telefono", ""),
                    direccion = formulario.cleaned_data.get("direccion", ""),
                    rut = formulario.cleaned_data["rut"]
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
    return render(request, "logout.html")


def error_404_view(request, exception):
    return redirect('inicio')

def error_500_view(request):
    return redirect("inicio")