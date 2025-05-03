from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Company, Client, Order, DeliveryPersonnel, OrderTracking

admin.site.register(Company)
admin.site.register(Client)
admin.site.register(Order)
admin.site.register(DeliveryPersonnel)
admin.site.register(OrderTracking)
