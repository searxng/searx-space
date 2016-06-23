from django.db import models

# Create your models here.
from urllib.parse import urlparse


class Instance(models.Model):
    url = models.URLField(max_length=200, blank=True, unique=True)
    hidden_service_url = models.URLField(max_length=200, blank=True)
    install_since = models.DateField()

    def __str__(self):
        if self.url is None or self.url == '':
            return self.hidden_service_url
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
        return self.subject


class Url(models.Model):
    url = models.URLField(max_length=1024, blank=True, unique=True)

    def __str__(self):
        return self.url


class InstanceTest(models.Model):
    # keys
    timestamp = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    url = models.ForeignKey(Url, on_delete=models.SET_NULL, null=True)
    # response time
    pretransfer_response_time = models.DurationField()
    total_response_time = models.DurationField()
    # SSL
    certificate = models.ForeignKey(Certificate, on_delete=models.SET_NULL, null=True)
    connection_error_message = models.CharField(max_length=256, blank=True)
    valid_ssl = models.BooleanField(default=True)
    # HTTP
    http_status_code = models.PositiveSmallIntegerField(null=True)
    # Searx
    valid_instance = models.BooleanField(default=True)
    searx_version = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["-timestamp", "instance", "url"]
        unique_together = (("timestamp", "instance", "url"),)


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
