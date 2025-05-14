# orders/management/commands/safe_migrate.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.utils import ProgrammingError
import sys

class Command(BaseCommand):
    help = 'Run migrations with error handling for duplicate tables'
    
    def handle(self, *args, **options):
        try:
            # First attempt normal migration
            self.stdout.write('Attempting normal migration...')
            call_command('migrate')
            self.stdout.write(self.style.SUCCESS('Migrations completed successfully'))
            
        except ProgrammingError as e:
            if 'already exists' in str(e):
                self.stdout.write(self.style.WARNING(f'Table already exists error: {e}'))
                
                # Extract the problematic table name if possible
                error_msg = str(e)
                if 'relation "orders_cart" already exists' in error_msg:
                    self.stdout.write('Attempting to fake the problematic migration...')
                    try:
                        call_command('migrate', 'orders', '0008_cart_visitor_order_visitor_user_alter_category_image_and_more', '--fake')
                        self.stdout.write(self.style.SUCCESS('Faked problematic migration'))
                        
                        # Now try to run remaining migrations
                        call_command('migrate')
                        self.stdout.write(self.style.SUCCESS('Remaining migrations completed'))
                        
                    except Exception as fake_error:
                        self.stdout.write(self.style.ERROR(f'Failed to fake migration: {fake_error}'))
                        # Try to continue with other apps
                        self.stdout.write('Attempting to migrate other apps...')
                        call_command('migrate', '--run-syncdb')
                        
                else:
                    # Generic handling for other duplicate table errors
                    self.stdout.write(self.style.WARNING('Unknown duplicate table error'))
                    sys.exit(1)
                    
            else:
                # Re-raise if it's not a duplicate table error
                raise
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
            sys.exit(1)