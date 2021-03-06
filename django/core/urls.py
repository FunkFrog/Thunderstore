from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.views.generic.base import RedirectView
from django.urls import path, include
from django.http import HttpResponse

from rest_framework import permissions

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from repository.urls import urlpatterns as repository_urls
from repository.views import PackageListView

from social.urls import settings_urls

from .api_urls import api_v1_urls


handler404 = "frontend.views.handle404"
handler500 = "frontend.views.handle500"

urlpatterns = [
    path('', PackageListView.as_view(), name="index"),
    path('auth/', include('social_django.urls', namespace='social')),
    path('logout/', LogoutView.as_view(), kwargs={'next_page': '/'}, name="logout"),
    path('package/', include(repository_urls)),
    path('settings/', include(settings_urls)),
    path('favicon.ico', RedirectView.as_view(url="%s%s" % (settings.STATIC_URL, 'favicon.ico'))),
    path('djangoadmin/', admin.site.urls),
    path('healthcheck/', lambda request: HttpResponse("OK"), name="healthcheck"),
    path('api/v1/', include((api_v1_urls, "api-v1"), namespace="api-v1")),
]

schema_view = get_schema_view(
   openapi.Info(
      title="Thunderstore API",
      default_version="v1",
      description="Schema is automatically generated and not completely accurate.",
      contact=openapi.Contact(name="Mythic#0001", url="https://discord.gg/5MbXZvd"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns += [
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="swagger"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
