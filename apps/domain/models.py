from django.db import models


class Domain(models.Model):
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=[('active', 'Active'), ('expiring', 'Expiring'), ('expired', 'Expired')])
    expiry_date = models.DateField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
