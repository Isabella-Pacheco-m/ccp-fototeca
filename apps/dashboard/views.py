from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts import servicios
from apps.accounts.forms import FormularioUsuario
from apps.core.permisos import solo_superadmin
from apps.gallery.models import Categoria, Fotografia

from .forms import FormularioCategoria, FormularioFotografia

Usuario = get_user_model()

POR_PAGINA = 20
BINARIOS = ("imagen", "miniatura")


# ------------------------------------------------------------------ inicio ---


@solo_superadmin
def inicio(request):
    fotos = Fotografia.objects.all()
    total = fotos.count()
    resumen_categorias = (
        Categoria.objects.annotate(total=Count("fotografias"))
        .filter(total__gt=0)
        .order_by("-total")[:6]
    )
    anios = list(fotos.values_list("anio", flat=True).order_by("anio").distinct())

    recientes = (
        fotos.select_related("categoria").defer(*BINARIOS).order_by("-creado_en")[:8]
    )
    peso_total = fotos.aggregate(total=Sum("imagen_peso"))["total"] or 0

    return render(
        request,
        "dashboard/inicio.html",
        {
            "total": total,
            "publicadas": fotos.filter(publicada=True).count(),
            "borradores": fotos.filter(publicada=False).count(),
            "total_usuarios": Usuario.objects.filter(is_active=True).count(),
            "total_superadmins": Usuario.objects.filter(rol=Usuario.Rol.SUPERADMIN, is_active=True).count(),
            "resumen_categorias": resumen_categorias,
            "recientes": recientes,
            "peso_total_mb": round(peso_total / 1024 / 1024, 1),
            "anio_min": anios[0] if anios else None,
            "anio_max": anios[-1] if anios else None,
        },
    )


# ------------------------------------------------------------- fotografías ---


@solo_superadmin
def fotografias(request):
    consulta = (request.GET.get("q") or "").strip()
    estado = request.GET.get("estado", "")
    categoria_slug = (request.GET.get("categoria") or "").strip()
    anio = (request.GET.get("anio") or "").strip()

    listado = Fotografia.objects.select_related("categoria", "subida_por").defer(*BINARIOS)
    if consulta:
        listado = listado.buscar(consulta)
    if estado == "publicadas":
        listado = listado.filter(publicada=True)
    elif estado == "borradores":
        listado = listado.filter(publicada=False)
    if categoria_slug:
        listado = listado.filter(categoria__slug=categoria_slug)
    if anio.isdigit():
        listado = listado.filter(anio=int(anio))

    paginador = Paginator(listado.order_by("-creado_en"), POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("pagina"))

    return render(
        request,
        "dashboard/fotografias.html",
        {
            "pagina": pagina,
            "total": paginador.count,
            "categorias": Categoria.objects.all(),
            "anios": Fotografia.objects.values_list("anio", flat=True).order_by("-anio").distinct(),
            "filtros": {"q": consulta, "estado": estado, "categoria": categoria_slug, "anio": anio},
        },
    )


@solo_superadmin
def fotografia_nueva(request):
    formulario = FormularioFotografia(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        foto = formulario.save(usuario=request.user)
        messages.success(request, f"«{foto.titulo}» se agregó a la fototeca.")
        if "guardar_y_seguir" in request.POST:
            return redirect("dashboard:fotografia_nueva")
        return redirect("dashboard:fotografias")

    return render(
        request,
        "dashboard/fotografia_form.html",
        {"formulario": formulario, "foto": None, "titulo_pagina": "Nueva fotografía"},
    )


@solo_superadmin
def fotografia_editar(request, pk):
    foto = get_object_or_404(Fotografia.objects.defer(*BINARIOS), pk=pk)
    formulario = FormularioFotografia(request.POST or None, request.FILES or None, instance=foto)
    if request.method == "POST" and formulario.is_valid():
        formulario.save(usuario=request.user)
        messages.success(request, "Cambios guardados.")
        return redirect("dashboard:fotografias")

    return render(
        request,
        "dashboard/fotografia_form.html",
        {"formulario": formulario, "foto": foto, "titulo_pagina": "Editar fotografía"},
    )


@solo_superadmin
def fotografia_eliminar(request, pk):
    foto = get_object_or_404(Fotografia.objects.defer(*BINARIOS), pk=pk)
    if request.method == "POST":
        titulo = foto.titulo
        foto.delete()
        messages.success(request, f"Se eliminó «{titulo}» de la fototeca.")
        return redirect("dashboard:fotografias")
    return render(request, "dashboard/fotografia_eliminar.html", {"foto": foto})


@solo_superadmin
@require_POST
def fotografia_publicacion(request, pk):
    foto = get_object_or_404(Fotografia.objects.defer(*BINARIOS), pk=pk)
    foto.publicada = not foto.publicada
    foto.save(update_fields=["publicada", "actualizado_en"])
    messages.success(
        request,
        f"«{foto.titulo}» ahora está {'publicada' if foto.publicada else 'como borrador'}.",
    )
    volver = request.POST.get("volver", "")
    if volver and url_has_allowed_host_and_scheme(volver, {request.get_host()}, request.is_secure()):
        return redirect(volver)
    return redirect("dashboard:fotografias")


# --------------------------------------------------------------- categorías ---


@solo_superadmin
def categorias(request):
    formulario = FormularioCategoria(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        categoria = formulario.save()
        messages.success(request, f"Categoría «{categoria.nombre}» creada.")
        return redirect("dashboard:categorias")

    listado = Categoria.objects.annotate(total=Count("fotografias")).order_by("orden", "nombre")
    return render(request, "dashboard/categorias.html", {"formulario": formulario, "categorias": listado})


@solo_superadmin
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    formulario = FormularioCategoria(request.POST or None, instance=categoria)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Categoría actualizada.")
        return redirect("dashboard:categorias")
    return render(
        request,
        "dashboard/categoria_form.html",
        {"formulario": formulario, "categoria": categoria},
    )


@solo_superadmin
@require_POST
def categoria_eliminar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    try:
        categoria.delete()
    except ProtectedError:
        messages.error(
            request,
            f"No se puede eliminar «{categoria.nombre}»: tiene fotografías asociadas. "
            "Reasígnalas o desactiva la categoría.",
        )
    else:
        messages.success(request, f"Categoría «{categoria.nombre}» eliminada.")
    return redirect("dashboard:categorias")


# ----------------------------------------------------------------- usuarios ---


@solo_superadmin
def usuarios(request):
    consulta = (request.GET.get("q") or "").strip()
    rol = request.GET.get("rol", "")
    estado = request.GET.get("estado", "")

    listado = Usuario.objects.all()
    if consulta:
        listado = listado.filter(
            Q(correo__icontains=consulta) | Q(nombre__icontains=consulta) | Q(cargo__icontains=consulta)
        )
    if rol in dict(Usuario.Rol.choices):
        listado = listado.filter(rol=rol)
    if estado == "activos":
        listado = listado.filter(is_active=True)
    elif estado == "inactivos":
        listado = listado.filter(is_active=False)

    paginador = Paginator(listado.order_by("-is_active", "nombre", "correo"), POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("pagina"))

    return render(
        request,
        "dashboard/usuarios.html",
        {
            "pagina": pagina,
            "total": paginador.count,
            "roles": Usuario.Rol.choices,
            "filtros": {"q": consulta, "rol": rol, "estado": estado},
        },
    )


@solo_superadmin
def usuario_nuevo(request):
    formulario = FormularioUsuario(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save(commit=False)
        usuario.set_unusable_password()  # el ingreso es por enlace mágico
        usuario.invitado_por = request.user
        usuario.save()
        messages.success(request, f"{usuario.correo} ya puede ingresar con enlace mágico.")

        if "enviar_enlace" in request.POST:
            return _enviar_enlace(request, usuario)
        return redirect("dashboard:usuarios")

    return render(
        request,
        "dashboard/usuario_form.html",
        {"formulario": formulario, "usuario_editado": None, "titulo_pagina": "Autorizar nuevo usuario"},
    )


@solo_superadmin
def usuario_editar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    formulario = FormularioUsuario(request.POST or None, instance=usuario)
    if request.method == "POST" and formulario.is_valid():
        error_autobloqueo = _autobloqueo(request, formulario)
        if error_autobloqueo:
            messages.error(request, error_autobloqueo)
        else:
            formulario.save()
            messages.success(request, "Usuario actualizado.")
            return redirect("dashboard:usuarios")

    return render(
        request,
        "dashboard/usuario_form.html",
        {"formulario": formulario, "usuario_editado": usuario, "titulo_pagina": "Editar usuario"},
    )


@solo_superadmin
@require_POST
def usuario_eliminar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
    elif _es_ultimo_superadmin(usuario):
        messages.error(request, "Debe existir al menos un superadministrador activo.")
    else:
        correo = usuario.correo
        usuario.delete()
        messages.success(request, f"Se revocó el acceso de {correo}.")
    return redirect("dashboard:usuarios")


@solo_superadmin
@require_POST
def usuario_acceso(request, pk):
    """Habilita o deshabilita el acceso sin borrar el registro."""
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes deshabilitar tu propia cuenta.")
    elif usuario.is_active and _es_ultimo_superadmin(usuario):
        messages.error(request, "Debe existir al menos un superadministrador activo.")
    else:
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        messages.success(
            request,
            f"El acceso de {usuario.correo} quedó {'habilitado' if usuario.is_active else 'deshabilitado'}.",
        )
    return redirect("dashboard:usuarios")


@solo_superadmin
@require_POST
def usuario_enviar_enlace(request, pk):
    return _enviar_enlace(request, get_object_or_404(Usuario, pk=pk))


def _enviar_enlace(request, usuario):
    if not usuario.is_active:
        messages.error(request, "El usuario está deshabilitado: habilítalo antes de enviarle el enlace.")
        return redirect("dashboard:usuarios")
    try:
        enviado = servicios.solicitar_enlace(request, usuario.correo)
    except servicios.ErrorEnvio as exc:
        messages.error(request, str(exc))
    else:
        if enviado:
            messages.success(request, f"Se envió un enlace de acceso a {usuario.correo}.")
        else:
            messages.error(request, "No fue posible enviar el enlace: revisa el estado de la cuenta.")
    return redirect("dashboard:usuarios")


def _es_ultimo_superadmin(usuario):
    if not usuario.es_superadmin or not usuario.is_active:
        return False
    return (
        Usuario.objects.filter(rol=Usuario.Rol.SUPERADMIN, is_active=True).exclude(pk=usuario.pk).count() == 0
    )


def _autobloqueo(request, formulario):
    """Impide que un superadministrador se deje a sí mismo sin acceso al panel."""
    if formulario.instance.pk != request.user.pk:
        return None
    if formulario.cleaned_data.get("rol") != Usuario.Rol.SUPERADMIN:
        return "No puedes quitarte a ti mismo el rol de superadministrador."
    if not formulario.cleaned_data.get("is_active"):
        return "No puedes deshabilitar tu propia cuenta."
    return None
