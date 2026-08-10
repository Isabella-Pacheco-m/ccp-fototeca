from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("", include(("apps.gallery.urls", "gallery"), namespace="gallery")),
    path("cuenta/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("panel/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("django-admin/", admin.site.urls),
    path("salud/", core_views.salud, name="salud"),
]

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
