from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def salud(request):
    """Endpoint de health-check para Railway."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        bd = "ok"
    except Exception as exc:  # pragma: no cover - depende del entorno
        return JsonResponse({"estado": "degradado", "bd": str(exc)}, status=503)
    return JsonResponse({"estado": "ok", "bd": bd})


def _error(request, codigo, titulo, mensaje, status):
    return render(
        request,
        "core/error.html",
        {"codigo": codigo, "titulo": titulo, "mensaje": mensaje},
        status=status,
    )


def error_403(request, exception=None):
    return _error(
        request, 403, "Acceso restringido",
        "Tu cuenta no tiene permisos para ver esta sección de la Fototeca.", 403,
    )


def error_404(request, exception=None):
    return _error(
        request, 404, "Página no encontrada",
        "El recurso que buscas no existe o fue retirado del archivo.", 404,
    )


def error_500(request):
    return _error(
        request, 500, "Error interno",
        "Ocurrió un problema al procesar tu solicitud. Intenta de nuevo en unos minutos.", 500,
    )
