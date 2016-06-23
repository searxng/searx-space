from django.contrib import admin

# Register your models here.
from .models import Instance, Engine, Query


class InstanceAdmin(admin.ModelAdmin):
    list_display = ('url', 'hidden_service_url', 'install_since')
    ordering = ('install_since',)


class EngineAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)


class QueryAdmin(admin.ModelAdmin):
    # search_fields = ['engine']
    list_display = ('engine', 'query', 'method', 'language', 'image_proxy', 'safesearch', 'locale')
    list_filter = ('method', 'language', 'engine')
    ordering = ('engine', 'query', 'method', 'language', 'image_proxy', 'safesearch', 'locale')


admin.site.register(Instance, InstanceAdmin)
admin.site.register(Engine, EngineAdmin)
admin.site.register(Query, QueryAdmin)
