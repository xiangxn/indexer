#!/bin/bash

# export PATH="/usr/local/opt/mongodb/bin:$PATH"

work_dir=~/work/mongodb

mongod --dbpath=${work_dir}/data --port=27017 --logpath=${work_dir}/log/mongo.log --bind_ip 127.0.0.1
