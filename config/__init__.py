"""Paquete de configuración del proyecto.

Usamos PyMySQL como conector de MySQL porque se instala con pip en Windows,
macOS y Linux sin compilar nada (a diferencia de mysqlclient).
"""
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # Si no está instalado, se puede usar SQLite (ver README).
    pass
