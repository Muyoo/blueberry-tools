#!/bin/bash

function info() {
    echo -e "\033[32m$1\033[0m"
}

source ./docker-compose.env

# Init Grafana
info "Initial Grafana"
# Unzip Grafana plugins
mkdir -p ${GRAFANA_HOME}/logs
mkdir -p ${GRAFANA_PLUGIN_HOME}

for zipFile in `ls ${GRAFANA_PLUGIN_ZIPS}`
do
    fullZipFilePath="${GRAFANA_PLUGIN_ZIPS}/${zipFile}"
    echo "Unzip ${zipFile}"
    unzip -q -o ${fullZipFilePath} -d ${GRAFANA_PLUGIN_HOME}
done


# Initial MySQL
info "Initial MySQL"
mkdir -p $MYSQL_HOME/data
mkdir -p $MYSQL_HOME/log

# Adjust the directory ownership because mysqld runs as the mysql
# user (uid=999) inside container.
# Note: Do not change the ownership on MacOS, since we are not running it by root.
# chown -R 999:999 $MYSQL_HOME/data
# chown -R 999:999 $MYSQL_HOME/log

# Initial TimescaleDB
info "Initial TimescaleDB"
mkdir -p $TIMESCALEDB_HOME/data

# Adjust the directory ownership because postgres runs as the postgres
# user (uid=70) inside container.
# chown 70:70 $TIMESCALEDB_HOME/data

info "Start containers to init configs"
./docker-compose-wrapper.sh up -d
sleep 10

info "Check ${TIMESCALEDB_CONTAINER_NAME} ${MYSQL_CONTAINER_NAME} status"
while true; do
    echo "[ ${TIMESCALEDB_CONTAINER_NAME} ] Check init status after 1 second"
    sleep 1s
    docker top $TIMESCALEDB_CONTAINER_NAME | grep "postgres: TimescaleDB"
    if [ $? -eq 0 ]; then
        break
    fi
done

info "Check ${MYSQL_CONTAINER_NAME} status"
while true; do
    echo "[ ${MYSQL_CONTAINER_NAME} ] Check init status after 1 second"
    sleep 1s
    docker top $MYSQL_CONTAINER_NAME | grep "mysqld"
    if [ $? -eq 0 ]; then
        break
    fi
done
info ${MYSQL_ROOT_PASSWORD}
docker exec -it ${MYSQL_CONTAINER_NAME} mysql -hlocalhost -uroot -p${MYSQL_ROOT_PASSWORD} -e "CREATE DATABASE ${GRAFANA_DATABASE}"

info "Adjust ${TIMESCALEDB_CONTAINER_NAME} logging configs"

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
PG_HBA_CONF=$TIMESCALEDB_HOME/data/pg_hba.conf

platform=`uname`
if [ ${platform} = "Darwin" ];then
    # MacOS
    sed -i "" "s/^#log_destination =/log_destination =/" $PG_CONF_FILE
    sed -i "" "s/^#logging_collector = off/logging_collector = on/" $PG_CONF_FILE
    sed -i "" "s/^#parallel_tuple_cost = .*/parallel_tuple_cost = ${CONFIG_PARALLEL_TUPLE_COST}/" $PG_CONF_FILE
else
    # Linux
    sed -i "s/^#log_destination =/log_destination =/" $PG_CONF_FILE
    sed -i "s/^#logging_collector = off/logging_collector = on/" $PG_CONF_FILE
    sed -i "s/^#parallel_tuple_cost = .*/parallel_tuple_cost = ${CONFIG_PARALLEL_TUPLE_COST}/" $PG_CONF_FILE
fi
echo "host    all             all             0.0.0.0/0            md5" >> ${PG_HBA_CONF}

info "Stop ${MYSQL_CONTAINER_NAME} ${TIMESCALEDB_CONTAINER_NAME} ${GRAFANA_CONTAINER_NAME}"
./docker-compose-wrapper.sh stop

info "All Done"