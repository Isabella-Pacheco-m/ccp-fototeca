"""
Procesamiento de imágenes: normaliza lo que sube el administrador antes de
guardarlo como binario en Postgres y genera la miniatura de la galería.
"""

import hashlib
import io

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps

MIME_POR_FORMATO = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class ImagenProcesada:
    """Resultado del procesamiento de un archivo subido."""

    def __init__(self, datos, mime, ancho, alto, checksum, miniatura, miniatura_mime, formato):
        self.datos = datos
        self.mime = mime
        self.ancho = ancho
        self.alto = alto
        self.checksum = checksum
        self.miniatura = miniatura
        self.miniatura_mime = miniatura_mime
        self.formato = formato

    @property
    def peso(self):
        return len(self.datos)


def _abrir(archivo):
    archivo.seek(0)
    try:
        imagen = Image.open(archivo)
        imagen.verify()  # detecta archivos corruptos o que no son imágenes
    except Exception as exc:
        raise ValidationError("El archivo no es una imagen válida.") from exc

    archivo.seek(0)
    imagen = Image.open(archivo)
    if imagen.format not in settings.FORMATOS_PERMITIDOS:
        permitidos = ", ".join(settings.FORMATOS_PERMITIDOS)
        raise ValidationError(f"Formato no admitido ({imagen.format}). Usa: {permitidos}.")
    return imagen


def _a_rgb(imagen):
    if imagen.mode in ("RGBA", "LA", "P"):
        fondo = Image.new("RGB", imagen.size, (255, 255, 255))
        convertida = imagen.convert("RGBA")
        fondo.paste(convertida, mask=convertida.split()[-1])
        return fondo
    if imagen.mode != "RGB":
        return imagen.convert("RGB")
    return imagen


def _codificar(imagen, formato, calidad):
    bufer = io.BytesIO()
    if formato == "PNG":
        imagen.save(bufer, format="PNG", optimize=True)
    else:
        imagen.save(bufer, format="JPEG", quality=calidad, optimize=True, progressive=True)
    return bufer.getvalue()


def procesar(archivo):
    """
    Valida, reorienta, redimensiona y comprime la imagen.
    Devuelve una ``ImagenProcesada`` lista para persistir.
    """
    maximo = settings.IMAGEN_TAMANIO_MAXIMO_MB * 1024 * 1024
    if archivo.size > maximo:
        raise ValidationError(
            f"La imagen pesa {archivo.size / 1024 / 1024:.1f} MB y el máximo permitido "
            f"es {settings.IMAGEN_TAMANIO_MAXIMO_MB} MB."
        )

    imagen = _abrir(archivo)
    formato_original = imagen.format
    imagen = ImageOps.exif_transpose(imagen)  # respeta la orientación de la cámara
    imagen = _a_rgb(imagen)

    # Versión de consulta: se limita el ancho para no almacenar originales enormes.
    principal = imagen.copy()
    if principal.width > settings.IMAGEN_ANCHO_MAXIMO:
        alto = round(principal.height * settings.IMAGEN_ANCHO_MAXIMO / principal.width)
        principal = principal.resize((settings.IMAGEN_ANCHO_MAXIMO, alto), Image.LANCZOS)

    formato_salida = "PNG" if formato_original == "PNG" and imagen.mode == "RGB" else "JPEG"
    datos = _codificar(principal, formato_salida, calidad=86)

    # Si el PNG resulta desproporcionado (fotografías), se guarda como JPEG.
    if formato_salida == "PNG" and len(datos) > 1_500_000:
        formato_salida = "JPEG"
        datos = _codificar(principal, "JPEG", calidad=86)

    miniatura_img = imagen.copy()
    miniatura_img.thumbnail((settings.MINIATURA_ANCHO, settings.MINIATURA_ANCHO * 2), Image.LANCZOS)
    miniatura = _codificar(miniatura_img, "JPEG", calidad=78)

    return ImagenProcesada(
        datos=datos,
        mime=MIME_POR_FORMATO[formato_salida],
        ancho=principal.width,
        alto=principal.height,
        checksum=hashlib.sha256(datos).hexdigest(),
        miniatura=miniatura,
        miniatura_mime="image/jpeg",
        formato=formato_salida,
    )
