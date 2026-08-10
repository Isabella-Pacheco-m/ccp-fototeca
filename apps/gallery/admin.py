from django.contrib import admin
from django.utils.html import format_html

from .models import Categoria, Fotografia


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "slug", "orden", "activa", "total_fotografias"]
    list_editable = ["orden", "activa"]
    prepopulated_fields = {"slug": ("nombre",)}
    search_fields = ["nombre"]

    @admin.display(description="fotografías")
    def total_fotografias(self, obj):
        return obj.fotografias.count()


@admin.register(Fotografia)
class FotografiaAdmin(admin.ModelAdmin):
    list_display = ["vista_previa", "titulo", "anio", "categoria", "publicada", "destacada", "creado_en"]
    list_display_links = ["vista_previa", "titulo"]
    list_filter = ["categoria", "anio", "publicada", "destacada"]
    search_fields = ["titulo", "descripcion"]
    readonly_fields = ["imagen_mime", "imagen_peso", "ancho", "alto", "checksum", "creado_en", "actualizado_en"]
    exclude = ["imagen", "miniatura", "indice_busqueda"]

    @admin.display(description="")
    def vista_previa(self, obj):
        return format_html(
            '<img src="{}" style="height:44px;border-radius:4px;object-fit:cover;">', obj.url_miniatura
        )

    def has_add_permission(self, request):
        # La carga de imágenes se hace desde el panel de la Fototeca.
        return False
