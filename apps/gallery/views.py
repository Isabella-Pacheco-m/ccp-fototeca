from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.http import http_date

from apps.core.permisos import acceso_galeria

from .models import Categoria, Fotografia

POR_PAGINA = 24

ORDENES = {
    "recientes": ("-anio", "-creado_en"),
    "antiguas": ("anio", "creado_en"),
    "titulo": ("titulo",),
    "cargadas": ("-creado_en",),
}

# Campos pesados: nunca se traen en los listados.
BINARIOS = ("imagen", "miniatura")


def _consulta_base(request):
    return (
        Fotografia.objects.visibles_para(request.user)
        .select_related("categoria")
        .defer(*BINARIOS)
    )


@acceso_galeria
def galeria(request):
    consulta = (request.GET.get("q") or "").strip()
    anio = (request.GET.get("anio") or "").strip()
    categoria_slug = (request.GET.get("categoria") or "").strip()
    orden = request.GET.get("orden") if request.GET.get("orden") in ORDENES else "recientes"

    fotografias = _consulta_base(request)

    if consulta:
        fotografias = fotografias.buscar(consulta)
    if anio.isdigit():
        fotografias = fotografias.filter(anio=int(anio))
    if categoria_slug:
        fotografias = fotografias.filter(categoria__slug=categoria_slug)

    fotografias = fotografias.order_by(*ORDENES[orden])

    total = fotografias.count()
    paginador = Paginator(fotografias, POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("pagina"))

    # Facetas calculadas sobre el catálogo visible completo, no sobre el filtro.
    catalogo = Fotografia.objects.visibles_para(request.user)
    anios = list(
        catalogo.values_list("anio", flat=True).order_by("-anio").distinct()
    )
    ve_borradores = request.user.is_authenticated and request.user.es_superadmin
    categorias = (
        Categoria.objects.filter(activa=True)
        .annotate(total=Count("fotografias", filter=None if ve_borradores else Q(fotografias__publicada=True)))
        .order_by("orden", "nombre")
    )

    filtros_activos = {
        "q": consulta,
        "anio": anio if anio.isdigit() else "",
        "categoria": categoria_slug,
        "orden": orden,
    }
    hay_filtros = bool(consulta or filtros_activos["anio"] or categoria_slug)

    return render(
        request,
        "gallery/galeria.html",
        {
            "pagina": pagina,
            "total": total,
            "total_catalogo": catalogo.count(),
            "anios": anios,
            "categorias": categorias,
            "filtros": filtros_activos,
            "hay_filtros": hay_filtros,
            "ordenes": [
                ("recientes", "Año, más reciente"),
                ("antiguas", "Año, más antiguo"),
                ("titulo", "Título (A–Z)"),
                ("cargadas", "Carga más reciente"),
            ],
        },
    )


@acceso_galeria
def detalle(request, pk):
    foto = get_object_or_404(
        Fotografia.objects.visibles_para(request.user).select_related("categoria", "subida_por").defer(*BINARIOS),
        pk=pk,
    )
    relacionadas = (
        Fotografia.objects.visibles_para(request.user)
        .select_related("categoria")
        .defer(*BINARIOS)
        .filter(categoria=foto.categoria)
        .exclude(pk=foto.pk)
        .order_by("-anio")[:6]
    )
    return render(request, "gallery/detalle.html", {"foto": foto, "relacionadas": relacionadas})


@acceso_galeria
def archivo(request, pk, variante):
    """Entrega el binario guardado en Postgres, con caché condicional."""
    if variante not in {"completa", "miniatura"}:
        raise Http404("Variante de imagen desconocida.")

    campos = ("id", "slug", "checksum", "actualizado_en", "publicada", "imagen_mime", "miniatura_mime")
    columna = "imagen" if variante == "completa" else "miniatura"
    foto = get_object_or_404(
        Fotografia.objects.visibles_para(request.user).only(*campos, columna),
        pk=pk,
    )

    datos = foto.imagen if variante == "completa" else foto.miniatura
    if datos is None:
        raise Http404("La fotografía no tiene archivo asociado.")

    mime = foto.imagen_mime if variante == "completa" else (foto.miniatura_mime or foto.imagen_mime)
    etag = f'"{foto.checksum or foto.pk}-{variante}"'

    if request.headers.get("If-None-Match") == etag:
        respuesta = HttpResponse(status=304)
        respuesta["ETag"] = etag
        return respuesta

    respuesta = HttpResponse(bytes(datos), content_type=mime)
    respuesta["ETag"] = etag
    respuesta["Last-Modified"] = http_date(foto.actualizado_en.timestamp())
    respuesta["Cache-Control"] = "private, max-age=604800"
    respuesta["Content-Disposition"] = f'inline; filename="{foto.slug or foto.pk}.jpg"'
    return respuesta


@acceso_galeria
def descargar(request, pk):
    foto = get_object_or_404(Fotografia.objects.visibles_para(request.user), pk=pk)
    extension = {"image/png": "png", "image/webp": "webp"}.get(foto.imagen_mime, "jpg")
    respuesta = HttpResponse(bytes(foto.imagen), content_type=foto.imagen_mime)
    respuesta["Content-Disposition"] = f'attachment; filename="{foto.slug or foto.pk}.{extension}"'
    return respuesta
