#!/usr/bin/env python
"""
Test script to verify database credentials.
Tests both credential sets mentioned in the project:
1. .env credentials: root:123456
2. Hardcoded credentials: 13892277786:ln20050924
"""

import os
import sys

# Add project to path and configure Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_search_project.settings')

# Load environment variables from .env if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env file")
except ImportError:
    print("python-dotenv not installed, skipping .env load")

try:
    import django
    django.setup()

    # Now we can use Django's database connection
    from django.db import connection

    print("=" * 60)
    print("Testing Database Connection via Django")
    print("=" * 60)

    # Get current database configuration
    from django.conf import settings
    db_config = settings.DATABASES['default']

    print(f"Database engine: {db_config['ENGINE']}")
    print(f"Database name: {db_config['NAME']}")
    print(f"Database user: {db_config['USER']}")
    print(f"Database host: {db_config['HOST']}:{db_config['PORT']}")
    print(f"Password: {db_config['PASSWORD'][:3]}*** (hidden for security)")

    # Test connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"\n[OK] Database connection successful! Test query result: {result}")
            print(f"[OK] Using credentials: {db_config['USER']}:{db_config['PASSWORD'][:3]}***")
    except Exception as e:
        print(f"\n[FAIL] Database connection failed: {e}")
        print(f"[FAIL] Failed with credentials: {db_config['USER']}:{db_config['PASSWORD'][:3]}***")

except Exception as e:
    print(f"Error setting up Django: {e}")
    print("Trying direct MySQLdb connection instead...")

    # Fallback to direct MySQLdb test
    try:
        import MySQLdb

        print("\n" + "=" * 60)
        print("Testing Direct MySQL Connection")
        print("=" * 60)

        # Test both credential sets directly
        credentials_sets = [
            ('root', '123456'),           # .env credentials
            ('13892277786', 'ln20050924')  # Hardcoded credentials
        ]

        for user, password in credentials_sets:
            try:
                conn = MySQLdb.connect(
                    host='localhost',
                    port=3306,
                    user=user,
                    password=password,
                    database='demo1'
                )
                conn.close()
                print(f"[OK] Success with credentials: {user}:{password[:3]}***")
            except Exception as e:
                print(f"[FAIL] Failed with {user}:{password[:3]}*** - Error: {e}")

    except ImportError:
        print("MySQLdb not available. Make sure mysqlclient or PyMySQL is installed.")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)