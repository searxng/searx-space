from django.db import models

# Create your models here.
from stats.url_utils import urlparse


class Instance(models.Model):
    url = models.URLField(max_length=200, blank=True)
    hidden_service_url = models.URLField(max_length=200, blank=True)
    install_since = models.DateField()

    def __str__(self):
        if self.url is None or self.url == '':
            return self.hidden_service_url
        else:
            return self.url


class Engine(models.Model):
    name = models.CharField(max_length=128, primary_key=True)
    description = models.TextField(max_length=2000, blank=True)

    def __str__(self):
        return self.name


class Query(models.Model):
    GET = 'GET'
    POST = 'POST'
    HTTP_METHODS = (
        (GET, 'GET'),
        (POST, 'POST'),
    )

    engine = models.ForeignKey(Engine, on_delete=models.CASCADE, db_column='engine_name')
    query = models.CharField(max_length=1024, blank=True)
    method = models.CharField(max_length=1024, blank=True, choices=HTTP_METHODS, default=GET)
    language = models.CharField(max_length=1024, blank=True)
    image_proxy = models.CharField(max_length=1024, blank=True)
    safesearch = models.CharField(max_length=1024, blank=True)
    locale = models.CharField(max_length=1024, blank=True)

    def __str__(self):
        return '[' + self.engine.name + '] ' + self.query


class Certificate(models.Model):
    signature = models.CharField(max_length=1024, blank=True)
    signature_algorithm = models.CharField(max_length=256, blank=True)
    start_date = models.DateField()
    expire_date = models.DateField()
    issuer = models.CharField(max_length=1024, blank=True)
    subject = models.CharField(max_length=1024, blank=True)
    cert = models.CharField(max_length=8192, blank=True)

    def __str__(self):
        if not hasattr(self, '_username'):
            self._username = self.issuer
            s = self.issuer.split(';')
            for p in s:
                if p.startswith(' CN=') or p.startswith('CN='):
                    p = p.split('=')
                    self._username = p[1]
                    break
            self._username = self._username + ' (' + str(self.expire_date) + ', ' + self.signature[0:8] + '...)'
        return self._username


class Url(models.Model):
    url = models.URLField(max_length=1024, blank=True, unique=True)

    def _get_urlparse(self):
        if not hasattr(self, '_urlparse'):
            self._urlparse = urlparse(self.url)
        return self._urlparse

    def netloc(self):
        if self.url is not None:
            return self._get_urlparse().netloc
        else:
            return ''

    def scheme(self):
        if self.url is not None:
            return self._get_urlparse().scheme
        else:
            return ''

    def __str__(self):
        return self.url

    class Meta:
        unique_together = (("url"),)


class ObjectCache():

    def __init__(self, object_class, load_all=False):
        self._object_class = object_class

        pk_to_obj = {}
        if load_all:
            for obj in object_class.objects.all():
                pk_to_obj[obj.pk] = obj
        self._pk_to_obj = pk_to_obj

    def get(self, pk):
        value = self._pk_to_obj.get(pk, None)
        if value is None:
            value = self._object_class.objects.get(id=pk)
            self._pk_to_obj[pk] = value
        return value


class UrlCache():

    def __init__(self):
        self._url_to_obj = {}
        self._pk_to_obj = {}
        for url in Url.objects.all():
            self._url_to_obj[url.url] = url
            self._pk_to_obj[url.pk] = url

    def url_to_obj(self, url, create=False):
        obj = self._url_to_obj.get(url, None)
        if obj is None and create:
            obj = Url(url=url)
            obj.save()
            self._url_to_obj[obj.url] = obj
            self._pk_to_obj[obj.pk] = obj
        return obj

    def url_to_pk(self, url, create=False):
        obj = self.url_to_obj(url, create)
        if obj is None:
            return None
        else:
            return obj.pk

    def pk_to_obj(self, pk):
        return self._pk_to_obj.get(pk, None)


URL_TYPE_HTTPS = 0
URL_TYPE_TOR = 1
URL_TYPE = (
    (URL_TYPE_HTTPS, 'HTTPS'),
    (URL_TYPE_TOR, 'Tor'),
)


class InstanceTest(models.Model):
    # keys
    timestamp = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    url_type = models.PositiveSmallIntegerField(choices=URL_TYPE)
    #
    aggregate_id = models.IntegerField()
    # extra
    url = models.ForeignKey(Url, on_delete=models.CASCADE, null=True)
    # response time
    pretransfer_response_time = models.DurationField()
    total_response_time = models.DurationField()
    # SSL
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, null=True)
    connection_error_message = models.CharField(max_length=256, blank=True)
    valid_ssl = models.BooleanField(default=True)
    # HTTP
    http_status_code = models.PositiveSmallIntegerField(null=True)
    # Searx
    valid_instance = models.BooleanField(default=True)
    searx_version = models.CharField(max_length=32, blank=True)

    def can_aggregate(self, other):
        if other is None:
            return False

        if self.instance.pk == other.instance.pk\
           and self.url.pk == other.url.pk\
           and self.certificate == other.certificate\
           and self.connection_error_message == other.connection_error_message\
           and self.valid_ssl == other.valid_ssl\
           and self.http_status_code == other.http_status_code\
           and self.valid_instance == other.valid_instance\
           and self.searx_version == other.searx_version:
            return True
        else:
            return False

    class Meta:
        unique_together = (("timestamp", "instance", "url_type"),)


class QueryTest(models.Model):
    # keys
    timestamp = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    url = models.ForeignKey(Url, on_delete=models.SET_NULL, null=True)
    query = models.ForeignKey(Query, on_delete=models.CASCADE)
    # response time
    pretransfer_response_time = models.DurationField()
    total_response_time = models.DurationField()
    # TCP
    connection_error_message = models.CharField(max_length=256, blank=True)
    # HTTP
    http_status_code = models.PositiveSmallIntegerField()
    # Result
    valid_result = models.BooleanField(default=True)
    result_count = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-timestamp", "instance", "query"]
        unique_together = (("timestamp", "instance", "url"),)

'''
class QueryTestResult(models.Model):
    query_test = models.ForeignKey(QueryTest, on_delete=models.CASCADE)
    rank = models.PositiveSmallIntegerField()
    url = models.ForeignKey(QueryResultUrl, on_delete=models.CASCADE)
'''
