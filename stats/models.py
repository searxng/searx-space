from django.db import models

# Create your models here.
from urllib.parse import urlparse

class Instance(models.Model):
    url = models.URLField(max_length=200, blank=True, unique=True)
    hidden_service_url = models.URLField(max_length=200, blank=True)
    install_since = models.DateField()

    def __str__(self):
        if self.url is None or self.url == '':
            return self.hidden_server_url
        else:
            return self.url

    def url_host(self):
        if self.url is not None:
            o = urlparse(self.url)
            return o.netloc
        else:
            return ''


class Engine(models.Model):
    name = models.CharField(max_length=128, primary_key=True)
    description = models.TextField(max_length=2000, blank=True)

    def __str__(self):
        return self.name


class Query(models.Model):
    GET = 'GET'
    POST = 'POST'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'
    HTTP_METHODS = (
        (GET, 'GET'),
        (POST, 'POST'),
        (HEAD, 'HEAD'),
        (OPTIONS, 'OPTIONS'),        
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
        return self.subject


class Url(models.Model):
    url = models.URLField(max_length=1024, blank=True, unique=True)

    def __str__(self):
        return self.url


class InstanceTest(models.Model):
    timestamp = models.DateField(auto_now_add=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    url = models.ForeignKey(Url, on_delete=models.SET_NULL, null=True)
    response_time = models.DurationField()
    http_result = models.PositiveSmallIntegerField()
    error_message = models.CharField(max_length=256, blank=True)
    certificate = models.ForeignKey(Certificate, on_delete=models.SET_NULL, null=True)
    valid_ssl = models.BooleanField(default=True)
    valid_instance = models.BooleanField(default=True)
    searx_version = models.CharField(max_length=32, blank=True)


class QueryTest(models.Model):
    timestamp = models.DateField(auto_now_add=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    query = models.ForeignKey(Query, on_delete=models.CASCADE)
    response_time = models.DurationField()
    http_result = models.PositiveSmallIntegerField()
    error_message = models.CharField(max_length=256, blank=True)
    result_count = models.PositiveSmallIntegerField()


'''
class QueryTestResult(models.Model):
    query_test = models.ForeignKey(QueryTest, on_delete=models.CASCADE)
    rank = models.PositiveSmallIntegerField()
    url = models.ForeignKey(QueryResultUrl, on_delete=models.CASCADE)
'''
