from django.conf import settings


def marca(request):
    """Datos institucionales disponibles en todas las plantillas."""
    return {
        "MARCA": {
            "nombre": "Fototeca",
            "entidad": "Cámara de Comercio de Palmira",
            "entidad_corta": "CCP",
            "descripcion": "Archivo fotográfico institucional",
        },
        "GALERIA_PUBLICA": settings.GALERIA_PUBLICA,
        "DEBUG": settings.DEBUG,
    }
