# orders/management/commands/safe_migrate.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.utils import ProgrammingError
import sys

class Command(BaseCommand):
    help = 'Run migrations with error handling for duplicate tables and missing columns'
    
    def handle(self, *args, **options):
        try:
            # First attempt normal migration
            self.stdout.write('Attempting normal migration...')
            call_command('migrate')
            self.stdout.write(self.style.SUCCESS('Migrations completed successfully'))
            
        except ProgrammingError as e:
            error_msg = str(e)
            
            if 'already exists' in error_msg:
                self.stdout.write(self.style.WARNING(f'Table already exists error: {e}'))
                
                # Extract the problematic table name if possible
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
            
            elif 'column "visitor_user_id" of relation "orders_order" does not exist' in error_msg:
                self.stdout.write(self.style.WARNING('Missing visitor_user_id column detected. Attempting to fix...'))
                
                try:
                    # First, check if we have a migration that adds this column
                    self.stdout.write('Checking for pending migrations...')
                    call_command('showmigrations', 'orders')
                    
                    # Try to create a migration specifically for this issue
                    self.stdout.write('Creating migration for visitor_user_id...')
                    call_command('makemigrations', 'orders', '--name', 'add_visitor_user_id_column')
                    
                    # Apply the new migration
                    self.stdout.write('Applying new migration...')
                    call_command('migrate', 'orders')
                    
                    self.stdout.write(self.style.SUCCESS('Successfully added visitor_user_id column'))
                
                except Exception as column_error:
                    self.stdout.write(self.style.ERROR(f'Failed to fix missing column: {column_error}'))
                    self.stdout.write('You may need to manually fix this issue by:')
                    self.stdout.write('1. Inspecting your models.py file')
                    self.stdout.write('2. Running python manage.py makemigrations orders')
                    self.stdout.write('3. Running python manage.py migrate orders')
                    sys.exit(1)
                    
            else:
                # Re-raise if it's not a handled error
                raise
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
            sys.exit(1)