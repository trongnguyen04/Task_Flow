CREATE DATABASE IF NOT EXISTS taskdb
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'taskflow_user'@'localhost'
IDENTIFIED BY 'taskflow123';

GRANT ALL PRIVILEGES ON taskdb.* TO 'taskflow_user'@'localhost';

FLUSH PRIVILEGES;
