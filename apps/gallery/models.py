import uuid
from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .utils import normalizar

ANIO_MINIMO = 1900


def anio_maximo():
    return date.today().year + 1


class Categoria(models.Model):
    """Clasificación institucional de las fotografías."""

    nombre = models.CharField("nombre", max_length=80, unique=True)
    slug = models.SlugField("identificador", max_length=90, unique=True, blank=True)
    descripcion = models.CharField("descripción", max_length=200, blank=True)
    color = models.CharField(
        "color de la etiqueta",
        max_length=7,
        default="#6B9A38",
        help_text="Color hexadecimal usado en la etiqueta de la galería.",
    )
    orden = models.PositiveSmallIntegerField("orden", default=0)
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)[:90]
        super().save(*args, **kwargs)


class FotografiaQuerySet(models.QuerySet):
    def publicadas(self):
        return self.filter(publicada=True)

    def visibles_para(self, usuario):
        """El superadministrador también ve los borradores."""
        if getattr(usuario, "is_authenticated", False) and usuario.es_superadmin:
            return self
        return self.publicadas()

    def buscar(self, consulta):
        termino = normalizar(consulta)
        if not termino:
            return self
        conjunto = self
        for palabra in termino.split():
            conjunto = conjunto.filter(indice_busqueda__contains=palabra)
        return conjunto


class Fotografia(models.Model):
    """
    Fotografía del archivo institucional.

    El binario vive en Postgres (``bytea``): el sistema de archivos de Railway
    es efímero, así que guardar la imagen en la base evita perderla en cada
    despliegue y mantiene una sola fuente de verdad para respaldos.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    titulo = models.CharField("título", max_length=180)
    slug = models.SlugField("identificador", max_length=200, blank=True)
    descripcion = models.TextField("descripción", blank=True)
    anio = models.PositiveIntegerField(
        "año",
        validators=[MinValueValidator(ANIO_MINIMO), MaxValueValidator(2100)],
        db_index=True,
    )
    categoria = models.ForeignKey(
        Categoria,
        verbose_name="categoría",
        on_delete=models.PROTECT,
        related_name="fotografias",
    )

    # --- binarios ---
    imagen = models.BinaryField("imagen", editable=False)
    imagen_mime = models.CharField(max_length=40, default="image/jpeg")
    imagen_peso = models.PositiveIntegerField("peso en bytes", default=0)
    ancho = models.PositiveIntegerField(default=0)
    alto = models.PositiveIntegerField(default=0)
    miniatura = models.BinaryField("miniatura", editable=False, null=True, blank=True)
    miniatura_mime = models.CharField(max_length=40, default="image/jpeg")
    checksum = models.CharField("SHA-256", max_length=64, blank=True, db_index=True)
    archivo_original = models.CharField("archivo original", max_length=255, blank=True)

    # --- publicación ---
    publicada = models.BooleanField("publicada", default=True, db_index=True)
    destacada = models.BooleanField("destacada", default=False)

    # --- trazabilidad ---
    subida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="subida por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fotografias",
    )
    creado_en = models.DateTimeField("creada", auto_now_add=True)
    actualizado_en = models.DateTimeField("actualizada", auto_now=True)

    # Texto normalizado (sin tildes) para el buscador.
    indice_busqueda = models.TextField(editable=False, blank=True)

    objects = FotografiaQuerySet.as_manager()

    class Meta:
        verbose_name = "fotografía"
        verbose_name_plural = "fotografías"
        ordering = ["-anio", "-creado_en"]
        indexes = [
            models.Index(fields=["-anio", "-creado_en"]),
            models.Index(fields=["categoria", "-anio"]),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.anio})"

    def get_absolute_url(self):
        return reverse("gallery:detalle", args=[self.pk])

    @property
    def url_imagen(self):
        return reverse("gallery:archivo", args=[self.pk, "completa"])

    @property
    def url_miniatura(self):
        return reverse("gallery:archivo", args=[self.pk, "miniatura"])

    @property
    def peso_legible(self):
        peso = self.imagen_peso or 0
        for unidad in ("B", "KB", "MB"):
            if peso < 1024 or unidad == "MB":
                return f"{peso:.0f} {unidad}" if unidad == "B" else f"{peso:.1f} {unidad}"
            peso /= 1024
        return f"{peso:.1f} MB"

    @property
    def proporcion(self):
        """Relación de aspecto para reservar espacio en la grilla."""
        if self.ancho and self.alto:
            return round(self.ancho / self.alto, 4)
        return 1.5

    def aplicar_imagen(self, procesada, nombre_original=""):
        """Vuelca el resultado de ``apps.core.imagenes.procesar`` en el modelo."""
        self.imagen = procesada.datos
        self.imagen_mime = procesada.mime
        self.imagen_peso = procesada.peso
        self.ancho = procesada.ancho
        self.alto = procesada.alto
        self.miniatura = procesada.miniatura
        self.miniatura_mime = procesada.miniatura_mime
        self.checksum = procesada.checksum
        if nombre_original:
            self.archivo_original = nombre_original[:255]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.titulo}-{self.anio}")[:200]
        categoria = self.categoria.nombre if self.categoria_id else ""
        self.indice_busqueda = normalizar(
            " ".join([self.titulo, self.descripcion, categoria, str(self.anio), self.archivo_original])
        )
        super().save(*args, **kwargs)
