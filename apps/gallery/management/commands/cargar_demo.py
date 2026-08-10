"""
Carga datos de demostración: categorías institucionales y fotografías de
ejemplo con título, descripción, año y categoría provisionales.

Uso:
    python manage.py cargar_demo
    python manage.py cargar_demo --limpiar        # rehace el catálogo demo
    python manage.py cargar_demo --carpeta ruta/  # otra carpeta de imágenes
"""

from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core import imagenes
from apps.gallery.models import Categoria, Fotografia

CATEGORIAS = [
    {
        "nombre": "Inauguración",
        "slug": "inauguracion",
        "descripcion": "Aperturas, cortes de cinta y puestas en servicio.",
        "color": "#6b9a38",
        "orden": 1,
    },
    {
        "nombre": "Sede",
        "slug": "sede",
        "descripcion": "Instalaciones y espacios de atención de la Cámara.",
        "color": "#9cb43a",
        "orden": 2,
    },
    {
        "nombre": "Evento",
        "slug": "evento",
        "descripcion": "Ferias, foros, capacitaciones y encuentros empresariales.",
        "color": "#3f6b26",
        "orden": 3,
    },
]

# Información provisional para la demostración.
FOTOGRAFIAS = [
    {
        "archivo": "Sede_Palmira-1024x682.jpg",
        "titulo": "Sede principal de Palmira",
        "descripcion": (
            "Fachada de la sede principal de la Cámara de Comercio de Palmira, "
            "centro de atención al empresariado del municipio."
        ),
        "anio": 2023,
        "categoria": "sede",
        "destacada": True,
    },
    {
        "archivo": "Sede_Candelaria.jpg",
        "titulo": "Sede Candelaria",
        "descripcion": "Instalaciones de la seccional Candelaria, que atiende al sector rural y agroindustrial.",
        "anio": 2021,
        "categoria": "sede",
    },
    {
        "archivo": "Sede_Florida.jpg",
        "titulo": "Sede Florida",
        "descripcion": "Punto de atención de la Cámara en el municipio de Florida, Valle del Cauca.",
        "anio": 2020,
        "categoria": "sede",
    },
    {
        "archivo": "Sede_Pradera.jpg",
        "titulo": "Sede Pradera",
        "descripcion": "Seccional de Pradera, donde se realizan trámites de registro mercantil y capacitaciones.",
        "anio": 2019,
        "categoria": "sede",
    },
    {
        "archivo": "Sede_Palmira-1024x682.jpg",
        "titulo": "Reapertura de la sede principal tras remodelación",
        "descripcion": (
            "Acto de reapertura de la sede principal después de la modernización de sus "
            "áreas de atención al público y salas de capacitación."
        ),
        "anio": 2023,
        "categoria": "inauguracion",
        "destacada": True,
    },
    {
        "archivo": "Sede_Candelaria.jpg",
        "titulo": "Inauguración de la sede Candelaria",
        "descripcion": (
            "Corte de cinta de la seccional Candelaria con la presencia de la junta directiva "
            "y autoridades municipales."
        ),
        "anio": 2021,
        "categoria": "inauguracion",
    },
    {
        "archivo": "Sede_Florida.jpg",
        "titulo": "Apertura del punto de atención en Florida",
        "descripcion": "Puesta en servicio del punto de atención de Florida para trámites empresariales.",
        "anio": 2020,
        "categoria": "inauguracion",
    },
    {
        "archivo": "Sede_Pradera.jpg",
        "titulo": "Inauguración de la seccional Pradera",
        "descripcion": "Ceremonia de apertura de la seccional Pradera junto a comerciantes de la región.",
        "anio": 2019,
        "categoria": "inauguracion",
    },
    {
        "archivo": "Sede_Palmira-1024x682.jpg",
        "titulo": "Rueda de negocios «Palmira Emprende»",
        "descripcion": (
            "Encuentro de compradores y proveedores locales organizado por la Cámara "
            "para dinamizar la economía del municipio."
        ),
        "anio": 2024,
        "categoria": "evento",
        "destacada": True,
    },
    {
        "archivo": "Sede_Florida.jpg",
        "titulo": "Feria empresarial del Valle del Cauca",
        "descripcion": "Participación de empresarios afiliados en la feria regional de exhibición comercial.",
        "anio": 2022,
        "categoria": "evento",
    },
    {
        "archivo": "Sede_Candelaria.jpg",
        "titulo": "Foro de formalización empresarial",
        "descripcion": (
            "Jornada de acompañamiento a comerciantes informales sobre registro mercantil "
            "y beneficios de la formalización."
        ),
        "anio": 2018,
        "categoria": "evento",
    },
    {
        "archivo": "Sede_Pradera.jpg",
        "titulo": "Encuentro anual de afiliados",
        "descripcion": "Reunión anual con los afiliados de la jurisdicción para presentar la rendición de cuentas.",
        "anio": 2017,
        "categoria": "evento",
    },
]


class Command(BaseCommand):
    help = "Carga categorías y fotografías de demostración en la fototeca."

    def add_arguments(self, parser):
        parser.add_argument(
            "--carpeta",
            default=str(settings.BASE_DIR / "imagenes-demo"),
            help="Carpeta con las imágenes de demostración.",
        )
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Elimina las fotografías existentes antes de cargar.",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        carpeta = Path(opciones["carpeta"])
        if not carpeta.is_dir():
            self.stderr.write(self.style.ERROR(f"No existe la carpeta {carpeta}"))
            return

        if opciones["limpiar"]:
            borradas, _ = Fotografia.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Se eliminaron {borradas} registros previos."))

        categorias = {}
        for datos in CATEGORIAS:
            categoria, creada = Categoria.objects.update_or_create(
                slug=datos["slug"],
                defaults={k: v for k, v in datos.items() if k != "slug"},
            )
            categorias[datos["slug"]] = categoria
            self.stdout.write(f"  {'+' if creada else '·'} categoría «{categoria.nombre}»")

        creadas = omitidas = 0
        for ficha in FOTOGRAFIAS:
            ruta = carpeta / ficha["archivo"]
            if not ruta.exists():
                self.stderr.write(self.style.WARNING(f"  ! falta el archivo {ruta.name}, se omite"))
                omitidas += 1
                continue

            if Fotografia.objects.filter(titulo=ficha["titulo"], anio=ficha["anio"]).exists():
                omitidas += 1
                continue

            with ruta.open("rb") as binario:
                subido = SimpleUploadedFile(ruta.name, binario.read())
                procesada = imagenes.procesar(subido)

            foto = Fotografia(
                titulo=ficha["titulo"],
                descripcion=ficha["descripcion"],
                anio=ficha["anio"],
                categoria=categorias[ficha["categoria"]],
                destacada=ficha.get("destacada", False),
                publicada=True,
            )
            foto.aplicar_imagen(procesada, ruta.name)
            foto.save()
            creadas += 1
            self.stdout.write(f"  + {foto.titulo} ({foto.anio}) · {foto.peso_legible}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {creadas} fotografías cargadas, {omitidas} omitidas. "
                f"Total en la fototeca: {Fotografia.objects.count()}."
            )
        )
