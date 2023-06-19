#!/bin/bash

if [ -z "$1" ]; then
  echo "Please set version!"
  exit 0
fi

VERSION=$1
WORKING_DIRECTORY=$(pwd)

function build_src {
  local name=$1

  local src="src/$name"
  local out="out/$name"

  local result="${name}_${VERSION}.zip"

  rm -rf "$out"
  mkdir -p "$out"
  cp -r "$src/lambda_handler.py" "$src/requirements.txt" "$out"
  cd "$out" || exit 1
  pip install --upgrade -r requirements.txt --target .
  zip -rqu "$result" .
  mv "$result" ../

  cd "$WORKING_DIRECTORY" || exit 1
}

build_src "process_feed"
build_src "process_events"

terraform apply -var='versions={"process_feed":"'"$VERSION"'","process_events":"'"$VERSION"'"}' -auto-approve
