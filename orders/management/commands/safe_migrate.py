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
            
            # New section to handle removing visitor_user_id - optimized for PostgreSQL on Render
            elif 'column visitor_user_id does not exist' in error_msg or 'relation "orders_order" does not exist' in error_msg:
                self.stdout.write(self.style.WARNING('Need to remove visitor_user_id column.'))
                
                try:
                    # Try to remove the column directly with PostgreSQL-specific SQL
                    from django.db import connection
                    self.stdout.write('Attempting to remove visitor_user_id column directly...')
                    with connection.cursor() as cursor:
                        # PostgreSQL syntax with additional safety checks
                        cursor.execute("""
                            DO $$
                            BEGIN
                                -- Check if the column exists before trying to drop it
                                IF EXISTS (
                                    SELECT 1 
                                    FROM information_schema.columns 
                                    WHERE table_name='orders_order' AND column_name='visitor_user_id'
                                ) THEN
                                    ALTER TABLE orders_order DROP COLUMN visitor_user_id;
                                    RAISE NOTICE 'Column visitor_user_id dropped successfully';
                                ELSE
                                    RAISE NOTICE 'Column visitor_user_id does not exist in table orders_order';
                                END IF;
                            END
                            $$;
                        """)
                        
                        self.stdout.write(self.style.SUCCESS('Successfully processed visitor_user_id column'))
                        
                except Exception as direct_sql_error:
                    self.stdout.write(self.style.WARNING(f'Could not remove column directly: {direct_sql_error}'))
                    
                    try:
                        # Create a specific migration as a fallback
                        self.stdout.write('Creating migration to remove visitor_user field...')
                        # First, create an empty migration file
                        call_command('makemigrations', 'orders', '--empty', '--name', 'remove_visitor_user_field')
                        
                        # Find the latest migration file
                        import os
                        from django.conf import settings
                        migrations_dir = os.path.join(settings.BASE_DIR, 'orders', 'migrations')
                        migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('_remove_visitor_user_field.py')]
                        
                        if migration_files:
                            # Sort to get the latest migration file
                            latest_migration = sorted(migration_files)[-1]
                            migration_path = os.path.join(migrations_dir, latest_migration)
                            
                            # Read the file content
                            with open(migration_path, 'r') as f:
                                content = f.read()
                            
                            # Replace the operations list with our SQL command
                            import re
                            new_content = re.sub(
                                r'operations = \[\s*\]',
                                '''operations = [
                                migrations.RunSQL(
                                    sql="""
                                    DO $$
                                    BEGIN
                                        -- Check if the column exists before trying to drop it
                                        IF EXISTS (
                                            SELECT 1 
                                            FROM information_schema.columns 
                                            WHERE table_name='orders_order' AND column_name='visitor_user_id'
                                        ) THEN
                                            ALTER TABLE orders_order DROP COLUMN visitor_user_id;
                                            RAISE NOTICE 'Column visitor_user_id dropped successfully';
                                        ELSE
                                            RAISE NOTICE 'Column visitor_user_id does not exist in table orders_order';
                                        END IF;
                                    END
                                    $$;
                                    """,
                                    reverse_sql="-- No reverse SQL provided"
                                )
                            ]''',
                                content
                            )
                            
                            # Write the updated content back to the file
                            with open(migration_path, 'w') as f:
                                f.write(new_content)
                            
                            # Apply the migration
                            self.stdout.write('Applying migration to remove visitor_user_id column...')
                            call_command('migrate', 'orders')
                            
                            self.stdout.write(self.style.SUCCESS('Successfully applied migration to remove visitor_user_id column'))
                        else:
                            self.stdout.write(self.style.ERROR('Could not find the created migration file'))
                        
                    except Exception as migration_error:
                        self.stdout.write(self.style.ERROR(f'Failed to create/apply migration: {migration_error}'))
                        sys.exit(1)
                
                # Now try to run remaining migrations
                try:
                    self.stdout.write('Running remaining migrations...')
                    call_command('migrate')
                except Exception as remaining_error:
                    self.stdout.write(self.style.WARNING(f'Error in remaining migrations: {remaining_error}'))
                    
            # Special case for handling both situations at once
            elif 'visitor_user_id' in error_msg:
                self.stdout.write(self.style.WARNING(f'Issue with visitor_user_id column detected: {error_msg}'))
                
                # Try to handle the column issue directly with PostgreSQL
                from django.db import connection
                with connection.cursor() as cursor:
                    # First check if the table exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'orders_order'
                        );
                    """)
                    table_exists = cursor.fetchone()[0]
                    
                    if table_exists:
                        # Check if column exists
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.columns 
                                WHERE table_name = 'orders_order' 
                                AND column_name = 'visitor_user_id'
                            );
                        """)
                        column_exists = cursor.fetchone()[0]
                        
                        if column_exists:
                            # Drop the column
                            self.stdout.write('Dropping visitor_user_id column...')
                            cursor.execute("ALTER TABLE orders_order DROP COLUMN visitor_user_id;")
                            self.stdout.write(self.style.SUCCESS('Dropped visitor_user_id column'))
                        else:
                            self.stdout.write('Column visitor_user_id does not exist')
                    else:
                        self.stdout.write('Table orders_order does not exist yet')
                
                # Try migrations again
                try:
                    self.stdout.write('Running migrations again...')
                    call_command('migrate')
                except Exception as retry_error:
                    self.stdout.write(self.style.WARNING(f'Error in retry migrations: {retry_error}'))
                    
            # Add handling for the missing orders_visitor table error
            elif 'relation "orders_visitor" does not exist' in error_msg:
                self.stdout.write(self.style.WARNING('Table orders_visitor does not exist. Creating migration for Visitor model...'))
                
                try:
                    # Create a migration for the Visitor model
                    self.stdout.write('Creating migration for Visitor model...')
                    call_command('makemigrations', 'orders')
                    
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
                            # Create the table based on the Visitor model definition
                            cursor.execute("""
                                CREATE TABLE IF NOT EXISTS orders_visitor (
                                    id SERIAL PRIMARY KEY,
                                    name VARCHAR(100) NOT NULL,
                                    phone_number VARCHAR(15) NOT NULL,
                                    email VARCHAR(254) NULL,
                                    user_id INTEGER NOT NULL UNIQUE REFERENCES orders_customuser(id) ON DELETE CASCADE
                                );
                            """)
                            self.stdout.write(self.style.SUCCESS('Created orders_visitor table directly'))
                    except Exception as direct_sql_error:
                        self.stdout.write(self.style.ERROR(f'Could not create table directly: {direct_sql_error}'))
                        sys.exit(1)
                        
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