from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Company, Client, Order, DeliveryPersonnel, OrderTracking,Category

admin.site.register(Company)
admin.site.register(Client)
admin.site.register(Order)
admin.site.register(DeliveryPersonnel)
admin.site.register(OrderTracking)
admin.site.register(Category)

from .models import DeliveryAddress, Order

@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'orders_count', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    def orders_count(self, obj):
        """Show number of orders using this address"""
        count = obj.order_set.count()
        return f"{count} order{'s' if count != 1 else ''}"
    orders_count.short_description = 'Orders Using This Address'
    
    def get_queryset(self, request):
        """Optimize queries by prefetching related orders"""
        return super().get_queryset(request).prefetch_related('order_set')
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion only if no orders are using this address"""
        if obj and obj.order_set.exists():
            return False
        return super().has_delete_permission(request, obj)

# Update your existing OrderAdmin if you have one
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client_name', 'company', 'delivery_address', 'status', 'ordered_at']
    list_filter = ['status', 'delivery_address', 'company', 'ordered_at']
    search_fields = ['client_name', 'client_email', 'delivery_address__name']
    ordering = ['-ordered_at']
    
    # Make delivery_address searchable
    autocomplete_fields = ['delivery_address'] if 'delivery_address' in [f.name for f in Order._meta.fields] else []

# Register the Order model if not already registered
# admin.site.register(Order, OrderAdmin)