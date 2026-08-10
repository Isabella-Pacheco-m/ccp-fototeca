"""
Crea (o actualiza) el superadministrador de la Fototeca.

Uso:
    python manage.py crear_superadmin --correo admin@ccpalmira.org.co --clave "…"
    ADMIN_CORREO=… ADMIN_CLAVE=… python manage.py crear_superadmin
"""

import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

Usuario = get_user_model()


class Command(BaseCommand):
    help = "Crea o actualiza el superadministrador de la Fototeca."

    def add_arguments(self, parser):
        parser.add_argument("--correo", default=os.getenv("ADMIN_CORREO"))
        parser.add_argument("--clave", default=os.getenv("ADMIN_CLAVE"))
        parser.add_argument("--nombre", default=os.getenv("ADMIN_NOMBRE", "Superadministrador"))

    def handle(self, *args, **opciones):
        correo = (opciones["correo"] or "").strip().lower()
        if not correo:
            self.stderr.write(self.style.ERROR("Indica --correo o la variable ADMIN_CORREO."))
            return

        clave = opciones["clave"]
        generada = False
        if not clave:
            clave = secrets.token_urlsafe(14)
            generada = True

        usuario, creado = Usuario.objects.get_or_create(
            correo=correo,
            defaults={"nombre": opciones["nombre"], "rol": Usuario.Rol.SUPERADMIN},
        )
        usuario.rol = Usuario.Rol.SUPERADMIN
        usuario.is_active = True
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.set_password(clave)
        usuario.save()

        self.stdout.write(
            self.style.SUCCESS(f"{'Creado' if creado else 'Actualizado'} el superadministrador {correo}.")
        )
        if generada:
            self.stdout.write(self.style.WARNING(f"Contraseña generada: {clave}"))
            self.stdout.write("Guárdala ahora: no se vuelve a mostrar.")
