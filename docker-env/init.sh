#!/bin/bash

# Initial MySQL
source ./docker-compose.env

mkdir -p $MYSQL_HOME/data
mkdir -p $MYSQL_HOME/log

# Adjust the directory ownership because mysqld runs as the mysql
# user (uid=999) inside container.
# Note: Do not change the ownership on MacOS, since we are not running it by root.
# chown -R 999:999 $MYSQL_HOME/data
# chown -R 999:999 $MYSQL_HOME/log

# Initial TimescaleDB
mkdir -p $TIMESCALEDB_HOME/data

# Adjust the directory ownership because postgres runs as the postgres
# user (uid=70) inside container.
# chown 70:70 $TIMESCALEDB_HOME/data

echo "Start $TIMESCALEDB_CONTAINER_NAME to init configs"

./docker-compose-wrapper.sh up -d

while true; do
    echo "Check init status after 1 second"
    sleep 1s
    docker top $TIMESCALEDB_CONTAINER_NAME | grep "postgres: TimescaleDB"
    if [ $? -eq 0 ]; then
        break
    fi
done

echo "Stop $TIMESCALEDB_CONTAINER_NAME"

./docker-compose-wrapper.sh stop

echo "Adjust logging configs"
#
# Activate the following settings to redirect logs to file.
#
#  log_destination = 'stderr'
#  logging_collector = on
#
# No need to tweak the following settings since they are default.
#
#  log_directory = 'log'
#  log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
#  log_rotation_age = 1d
#  log_rotation_size = 10MB
#  log_min_messages = warning
#  log_min_error_statement = error
# 
# Change the following settings to prefer to using parallel quring plan
# 
#  parallel_tuple_cost = 0.01
PG_CONF_FILE=$TIMESCALEDB_HOME/data/postgresql.conf

platform=`uname`
if [ ${platform} = "Darwin" ];then
    # MacOS
    sed -i "" 's/^#log_destination =/log_destination =/' $PG_CONF_FILE
    sed -i "" 's/^#logging_collector = off/logging_collector = on/' $PG_CONF_FILE
    sed -i "" 's/^#parallel_tuple_cost = .*/parallel_tuple_cost = 0.01/' $PG_CONF_FILE
else
    # Linux
    sed -i 's/^#log_destination =/log_destination =/' $PG_CONF_FILE
    sed -i 's/^#logging_collector = off/logging_collector = on/' $PG_CONF_FILE
    sed -i 's/^#parallel_tuple_cost = .*/parallel_tuple_cost = 0.01/' $PG_CONF_FILE
fi

echo "Done"