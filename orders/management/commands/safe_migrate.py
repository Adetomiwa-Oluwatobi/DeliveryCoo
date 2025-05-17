# orders/management/commands/safe_migrate.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.utils import ProgrammingError
import sys

class Command(BaseCommand):
    help = 'Run migrations with error handling for duplicate tables and missing columns'
    
    def handle(self, *args, **options):
        try:
            # Check for any unmigrated model changes
            self.stdout.write('Checking for unmigrated model changes...')
            call_command('makemigrations', '--check', interactive=False)
            
            # First attempt normal migration
            self.stdout.write('Attempting normal migration...')
            call_command('migrate')
            self.stdout.write(self.style.SUCCESS('Migrations completed successfully'))
            
        except ProgrammingError as e:
            error_msg = str(e)
            
            # Add handling for the missing orders_visitor table error - enhanced version
            if 'relation "orders_visitor" does not exist' in error_msg:
                self.stdout.write(self.style.WARNING('Table orders_visitor does not exist. Creating migration for Visitor model...'))
                
                try:
                    # First, check if there are any pending migrations
                    self.stdout.write('Checking for existing migrations...')
                    call_command('showmigrations', 'orders')
                    
                    # Create a migration for the Visitor model if needed
                    self.stdout.write('Creating migration for Visitor model...')
                    call_command('makemigrations', 'orders', '--name', 'create_visitor_model')
                    
                    # Apply the migrations
                    self.stdout.write('Applying migrations...')
                    call_command('migrate', 'orders')
                    
                    self.stdout.write(self.style.SUCCESS('Successfully created and applied migration for Visitor model'))
                    
                    # Try running all migrations again
                    try:
                        self.stdout.write('Running remaining migrations...')
                        call_command('migrate')
                    except Exception as remaining_error:
                        self.stdout.write(self.style.WARNING(f'Error in remaining migrations: {remaining_error}'))
                
                except Exception as migration_error:
                    self.stdout.write(self.style.ERROR(f'Failed to create/apply migration: {migration_error}'))
                    
                    # Try a manual approach to create the table
                    try:
                        from django.db import connection
                        self.stdout.write('Attempting to create orders_visitor table directly...')
                        with connection.cursor() as cursor:
                            # Check first if the table already exists
                            cursor.execute("""
                                SELECT EXISTS (
                                    SELECT FROM information_schema.tables 
                                    WHERE table_name = 'orders_visitor'
                                );
                            """)
                            table_exists = cursor.fetchone()[0]
                            
                            if not table_exists:
                                # Create the table based on the Visitor model definition
                                cursor.execute("""
                                    CREATE TABLE IF NOT EXISTS orders_visitor (
                                        id SERIAL PRIMARY KEY,
                                        phone_number VARCHAR(15) NOT NULL,
                                        user_id INTEGER NOT NULL UNIQUE REFERENCES orders_customuser(id) ON DELETE CASCADE
                                    );
                                """)
                                self.stdout.write(self.style.SUCCESS('Created orders_visitor table directly'))
                    except Exception as direct_sql_error:
                        self.stdout.write(self.style.ERROR(f'Could not create table directly: {direct_sql_error}'))
                        sys.exit(1)
            
            elif 'already exists' in error_msg:
                # Handle duplicate table errors as before
                # ...existing code...
                pass
                
            elif 'column "visitor_user_id" of relation "orders_order" does not exist' in error_msg:
                # Existing code for visitor_user_id column
                # ...existing code...
                pass
                
            # Special case for handling both situations at once
            elif 'visitor_user_id' in error_msg:
                # Existing code for visitor_user_id issues
                # ...existing code...
                pass
                        
            else:
                # Re-raise if it's not a handled error
                raise
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))
            # Even with errors, try to apply any remaining migrations as a fallback
            try:
                self.stdout.write('Attempting to apply any remaining migrations...')
                call_command('migrate', '--fake-initial')
            except Exception as final_error:
                self.stdout.write(self.style.ERROR(f'Final migration attempt failed: {final_error}'))
            sys.exit(1)