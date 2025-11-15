#!/bin/bash
#
# Trying to discover local repo dir
#
if [[ $1 == "stop"  ||  $1 == "STOP" ]]; then
  run="STOP"
else
  run="START"
fi

# repo_local_dir=""

# if [ $0 == "./start.sh" ] || [ $0 == "start.sh" ] || [ $0 == "infra/start.sh" ] || [ $0 == "./infra/start.sh" ]; then
#   repo_local_dir=`pwd | sed 's/infra//'`
# else
#   repo_local_dir=`echo $0 | sed 's/infra\/start\.sh//'`
# fi

# if [ ${repo_local_dir:0-1} != "/" ]; then
#   repo_local_dir="${repo_local_dir}/"
# fi

# if [ ${repo_local_dir} == "/" ]; then
#   echo "- Error: I couldn't discover local dir where this repo is cloned."
#   exit
# else
#   echo "- Discovered Repo Local dir as: ${repo_local_dir}"
# fi

source ~/.bashrc

#
# Install Docker colima if it's not installed already
#
echo "- Initializing... please wait... (this might take 5-10 minutes if you don't have colima installed)"
colima version > /dev/null 2>&1 || brew install colima > /dev/null 2>&1
docker version > /dev/null 2>&1 || brew install docker > /dev/null 2>&1
liquibase -v > /dev/null 2>&1 || brew install liquibase > /dev/null 2>&1

if [ `colima status 2>&1| grep -v "not running" | wc -l` -eq 0 ]; then
  echo "--- Starting colima..."
  colima start > /dev/null 2>&1
fi

docker context use colima > /dev/null 2>&1
sed  '/credsStore/d' ~/.docker/config.json > ~/config.json
mv ~/config.json ~/.docker/config.json

if [ $run == "START" ]; then
  docker-compose up -d
else
  docker-compose down
fi
