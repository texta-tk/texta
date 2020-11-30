from django.db import models


class CoreVariable(models.Model):
    name = models.CharField(max_length=1000)
    value = models.CharField(max_length=1000, default=None, null=True)


    def __str__(self):
        return f"{self.name} - {self.value}"
