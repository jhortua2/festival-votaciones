-- Crea la base de datos y un usuario para el proyecto.
-- Ejecútelo UNA vez como root: en MySQL Workbench, en phpMyAdmin (pestaña SQL)
-- o en consola:  mysql -u root -p < crear_bd.sql

CREATE DATABASE IF NOT EXISTS festival_votaciones
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'festival'@'localhost' IDENTIFIED BY 'festival2027';

GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival'@'localhost';
-- Permiso para que "python manage.py test" cree su base de pruebas:
GRANT ALL PRIVILEGES ON test_festival_votaciones.* TO 'festival'@'localhost';

FLUSH PRIVILEGES;
