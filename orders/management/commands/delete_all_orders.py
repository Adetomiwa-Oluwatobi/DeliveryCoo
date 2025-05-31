from django.core.management.base import BaseCommand
from orders.models import Order

class Command(BaseCommand):
    help = 'Delete all Order records'

    def handle(self, *args, **kwargs):
        count, _ = Order.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} orders.'))
