#!/bin/bash

if [ -z "$1" ]
then
  echo "Please set version!"
  exit 0
else
  VERSION=$1
fi

function build_src {
    local name=$1

    local src="src/$name"
    local out="out/$name"

    local result="${name}_${VERSION}.zip"

    rm -rf "$out"
    mkdir -p "$out"
    cp -r "$src/$name.py" "$src/requirements.txt" "$out"
    cd "$out" || exit 1
    pip install --upgrade -r requirements.txt --target .
    zip -rqu "$result" .
    mv "$result" ../
}

build_src "process_feed"
