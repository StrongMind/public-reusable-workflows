#!/bin/bash
if [ ! -f /var/run/postgresql/.started ]; then
    su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D /var/lib/postgresql/data -l /var/log/postgresql/postgresql.log start"
    sleep 2
    su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""
    
    # Recreate template1 with UTF8 encoding if it's using SQL_ASCII
    su - postgres -c "psql -c \"UPDATE pg_database SET datistemplate = FALSE WHERE datname = 'template1';\""
    su - postgres -c "psql -c \"DROP DATABASE IF EXISTS template1;\""
    su - postgres -c "psql -c \"CREATE DATABASE template1 WITH TEMPLATE = template0 ENCODING = 'UTF8' LC_COLLATE = 'C.UTF-8' LC_CTYPE = 'C.UTF-8';\""
    su - postgres -c "psql -c \"UPDATE pg_database SET datistemplate = TRUE WHERE datname = 'template1';\""
    
    su - postgres -c "psql -c \"CREATE DATABASE app;\""
    touch /var/run/postgresql/.started
fi

