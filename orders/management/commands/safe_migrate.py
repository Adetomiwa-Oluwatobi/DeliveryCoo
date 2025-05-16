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
                # Handle duplicate table errors as before
                # ...existing code...
                pass
                
            elif 'column "visitor_user_id" of relation "orders_order" does not exist' in error_msg:
                self.stdout.write(self.style.WARNING('Missing visitor_user_id column detected.'))
                
                # First try to find and apply an existing migration that adds this field
                self.stdout.write('Checking for existing migrations...')
                # Check if there are pending migrations
                call_command('showmigrations', 'orders')
                
                try:
                    # Try first to manually add just the column with SQL
                    from django.db import connection
                    self.stdout.write('Attempting to add column directly...')
                    with connection.cursor() as cursor:
                        # Try to add the column if it doesn't exist
                        # Note: This approach varies by database backend
                        cursor.execute("""
                            DO $$
                            BEGIN
                                BEGIN
                                    ALTER TABLE orders_order ADD COLUMN visitor_user_id integer REFERENCES auth_user(id) ON DELETE SET NULL;
                                EXCEPTION
                                    WHEN duplicate_column THEN
                                        RAISE NOTICE 'Column visitor_user_id already exists';
                                END;
                            END $$;
                        """)
                        self.stdout.write(self.style.SUCCESS('Added visitor_user_id column directly'))
                except Exception as direct_sql_error:
                    self.stdout.write(self.style.WARNING(f'Could not add column directly: {direct_sql_error}'))
                    
                    try:
                        # Create a specific migration as a fallback
                        self.stdout.write('Creating migration for visitor_user field...')
                        call_command('makemigrations', 'orders', '--name', 'add_visitor_user_field')
                        
                        # Apply the new migration
                        self.stdout.write('Applying new migration...')
                        call_command('migrate', 'orders')
                        
                        self.stdout.write(self.style.SUCCESS('Successfully added visitor_user_id column through migration'))
                    except Exception as migration_error:
                        self.stdout.write(self.style.ERROR(f'Failed to create/apply migration: {migration_error}'))
                        sys.exit(1)
                
                # Now try to run remaining migrations
                try:
                    self.stdout.write('Running remaining migrations...')
                    call_command('migrate')
                except Exception as remaining_error:
                    self.stdout.write(self.style.WARNING(f'Error in remaining migrations: {remaining_error}'))
                    
            else:
                # Re-raise if it's not a handled error
                raise
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
            sys.exit(1)