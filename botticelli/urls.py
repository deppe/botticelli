"""botticelli URL Configuration"""

from django.conf.urls import url
from django.contrib import admin
from botticelli import views

admin.autodiscover()

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^slack/slash$', views.slack_slash),
    url(r'^slack/action$', views.slack_action),
    url(r'^ping$', views.ping)
]
