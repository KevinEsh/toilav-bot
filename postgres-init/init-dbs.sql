SELECT 'CREATE DATABASE tremenda-test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'tremenda-test')\gexec