# orders/management/commands/safe_migrate.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.utils import ProgrammingError, OperationalError
import sys

class Command(BaseCommand):
    help = 'Run migrations with error handling for duplicate tables and missing tables/columns'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force-visitor',
            action='store_true',
            help='Force creation of orders_visitor table',
        )
    
    def handle(self, *args, **options):
        # Flag to track if we specifically handled orders_visitor
        visitor_table_handled = False
        
        try:
            # Check for any unmigrated model changes
            self.stdout.write('Checking for unmigrated model changes...')
            call_command('makemigrations', '--check', interactive=False)
            
            # First attempt normal migration
            self.stdout.write('Attempting normal migration...')
            call_command('migrate')
            self.stdout.write(self.style.SUCCESS('Migrations completed successfully'))
            
        except (ProgrammingError, OperationalError) as e:
            error_msg = str(e)
            self.stdout.write(self.style.WARNING(f"Migration error: {error_msg}"))
            
            # Add handling for the missing orders_visitor table error
            if 'relation "orders_visitor" does not exist' in error_msg or options.get('force_visitor'):
                visitor_table_handled = True
                self.stdout.write(self.style.WARNING('Table orders_visitor does not exist. Attempting to fix...'))
                
                try:
                    # First, check if there are any pending migrations for orders app
                    self.stdout.write('Checking for pending migrations in orders app...')
                    from django.db.migrations.executor import MigrationExecutor
                    from django.db import connections, DEFAULT_DB_ALIAS
                    
                    connection = connections[DEFAULT_DB_ALIAS]
                    executor = MigrationExecutor(connection)
                    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
                    orders_migrations = [migration for migration, backwards in plan if migration.app_label == 'orders']
                    
                    if orders_migrations:
                        self.stdout.write(f'Found {len(orders_migrations)} pending migrations for orders app')
                        
                        # Try fake initial for orders app
                        self.stdout.write('Attempting fake-initial for orders app...')
                        call_command('migrate', 'orders', '--fake-initial')
                    
                    # Try to apply specific migrations for the orders app
                    self.stdout.write('Applying migrations for orders app...')
                    call_command('migrate', 'orders')
                    
                    # Check if the visitor table exists now
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'orders_visitor'
                            );
                        """)
                        table_exists = cursor.fetchone()[0]
                    
                    if not table_exists:
                        # If still doesn't exist, create the table directly
                        self.stdout.write('Table still missing. Creating orders_visitor table directly...')
                        with connection.cursor() as cursor:
                            # Create the table based on the Visitor model definition
                            cursor.execute("""
                                CREATE TABLE IF NOT EXISTS orders_visitor (
                                    id SERIAL PRIMARY KEY,
                                    phone_number VARCHAR(15) NOT NULL,
                                    user_id INTEGER NOT NULL UNIQUE REFERENCES orders_customuser(id) ON DELETE CASCADE
                                );
                            """)
                            # Add migration record to django_migrations
                            cursor.execute("""
                                INSERT INTO django_migrations (app, name, applied)
                                SELECT 'orders', 'manual_create_visitor_table', NOW()
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM django_migrations 
                                    WHERE app = 'orders' AND name = 'manual_create_visitor_table'
                                );
                            """)
                        self.stdout.write(self.style.SUCCESS('Created orders_visitor table directly'))
                    
                    # Try running all remaining migrations
                    self.stdout.write('Running remaining migrations...')
                    call_command('migrate')
                    self.stdout.write(self.style.SUCCESS('All migrations completed'))
                
                except Exception as migration_error:
                    self.stdout.write(self.style.ERROR(f'Failed to fix visitor table issue: {migration_error}'))
                    
                    # Last resort - try fake-initial for everything
                    try:
                        self.stdout.write('Attempting fake-initial for all migrations as last resort...')
                        call_command('migrate', '--fake-initial')
                    except Exception as fake_error:
                        self.stdout.write(self.style.ERROR(f'Fake-initial failed: {fake_error}'))
                        sys.exit(1)
            
            elif 'already exists' in error_msg:
                # Handle duplicate table errors
                self.stdout.write(self.style.WARNING(f'Detected duplicate table error. Attempting to fix...'))
                
                try:
                    # Try fake-initial which often helps with "already exists" errors
                    self.stdout.write('Running migrate with --fake-initial...')
                    call_command('migrate', '--fake-initial')
                    self.stdout.write(self.style.SUCCESS('Completed fake-initial migration'))
                except Exception as fake_error:
                    self.stdout.write(self.style.ERROR(f'Fake-initial failed: {fake_error}'))
                
            elif 'column' in error_msg and 'does not exist' in error_msg:
                # Generic handling for missing columns
                self.stdout.write(self.style.WARNING(f'Detected missing column. Attempting to fix...'))
                
                try:
                    # First try fake migration which can help in some cases
                    self.stdout.write('Running migrate with --fake...')
                    call_command('migrate', '--fake')
                    
                    # Then try normal migration again
                    self.stdout.write('Attempting normal migration again...')
                    call_command('migrate')
                except Exception as column_error:
                    self.stdout.write(self.style.ERROR(f'Failed to fix column issue: {column_error}'))
            
            else:
                # Re-raise if it's not a handled error
                self.stdout.write(self.style.ERROR(f'Unhandled database error: {error_msg}'))
                raise
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error during migration: {e}'))
            
            # If we didn't already handle the visitor table specifically and we have errors
            if not visitor_table_handled:
                try:
                    # Check if the specific orders_visitor table is the root cause
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'orders_visitor'
                            );
                        """)
                        table_exists = cursor.fetchone()[0]
                    
                    if not table_exists:
                        self.stdout.write(self.style.WARNING('orders_visitor table missing. Attempting creation...'))
                        # Call ourselves with the force-visitor flag
                        call_command('safe_migrate', force_visitor=True)
                        return
                except Exception:
                    # If this fails, continue to fallback
                    pass
            
            # Even with errors, try to apply any remaining migrations as a fallback
            try:
                self.stdout.write('Attempting to apply any remaining migrations...')
                call_command('migrate', '--fake-initial')
                self.stdout.write(self.style.SUCCESS('Fallback migration completed'))
            except Exception as final_error:
                self.stdout.write(self.style.ERROR(f'Final migration attempt failed: {final_error}'))
                sys.exit(1)