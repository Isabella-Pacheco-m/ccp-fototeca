from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import EnlaceMagico, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["correo"]
    list_display = ["correo", "nombre", "rol", "is_active", "ultimo_ingreso", "total_ingresos"]
    list_filter = ["rol", "is_active"]
    search_fields = ["correo", "nombre", "cargo"]
    readonly_fields = ["date_joined", "ultimo_ingreso", "total_ingresos", "supabase_uid"]
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Datos", {"fields": ("nombre", "cargo", "notas")}),
        ("Acceso", {"fields": ("rol", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Trazabilidad", {"fields": ("date_joined", "ultimo_ingreso", "total_ingresos", "supabase_uid")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("correo", "nombre", "rol", "password1", "password2")}),
    )


@admin.register(EnlaceMagico)
class EnlaceMagicoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "creado_en", "expira_en", "usado_en", "ip_solicitud"]
    list_filter = ["creado_en", "usado_en"]
    search_fields = ["usuario__correo"]
    readonly_fields = [f.name for f in EnlaceMagico._meta.fields]

    def has_add_permission(self, request):
        return False
