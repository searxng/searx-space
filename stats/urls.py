from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^instance/([0-9]+)/$', views.instance, name='instance'),
    url(r'^engines$', views.engine_list, name='engine_list'),
    url(r'^engine/([a-zA-A0-9\-\_]+)/$', views.engine, name='engine'),
]
