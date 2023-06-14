#!/bin/bash

mkdir -p out/process_feed
cp -r src/process_feed/process_feed.py src/process_feed/requirements.txt out/process_feed
cd out/process_feed || exit
pip install --upgrade -r requirements.txt --target .
zip -rqu process_feed.zip .
