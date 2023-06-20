#!/bin/bash

if [ -z "$1" ]; then
  echo "Please set version!"
  exit 0
fi

VERSION=$1

terraform -chdir=terraform destroy -var='versions={"process_feed":"'"$VERSION"'","process_events":"'"$VERSION"'"}' -auto-approve
