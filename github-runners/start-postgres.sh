#!/bin/bash
if [ ! -f /var/run/postgresql/.started ]; then
    su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D /var/lib/postgresql/data -l /var/log/postgresql/postgresql.log start"
    sleep 2
    su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""
    su - postgres -c "psql -c \"CREATE DATABASE app;\""
    touch /var/run/postgresql/.started
fi

