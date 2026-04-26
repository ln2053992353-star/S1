try:
    import pymysql
    # Patch version to satisfy Django's mysqlclient version check
    # Django requires mysqlclient >= 2.2.1, so we set a compatible version
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.__version__ = "2.2.1"

    pymysql.install_as_MySQLdb()
    print("PyMySQL configured as MySQLdb compatibility layer (version patched for Django compatibility)")
except ImportError:
    # mysqlclient should be used if PyMySQL is not available
    print("PyMySQL not available, using mysqlclient if installed")
    pass