#!/bin/bash

if [ -z "$1" ]; then
  echo "Please set version!"
  exit 0
fi

VERSION=$1
WORKING_DIRECTORY=$(pwd)
BUCKET_NAME="dmm-integration"

function deploy_src {
  local name=$1
  local src="src/$name"
  local out="out/$name"
  local result="${name}_${VERSION}.zip"

  # clean
  rm -rf "$out"
  mkdir -p "$out"

  # copy sources
  cp -r "$src/lambda_handler.py" "$src/requirements.txt" "$out"
  cd "$out" || exit 1

  # install dependencies
  python3.10 -m pip install --upgrade -r requirements.txt --target .

  # bundle
  zip -rqu "$result" .

  # copy to s3
  aws s3 cp "$result" "s3://$BUCKET_NAME/$name/src/${VERSION}/lambda.zip"

  # back to working directory
  cd "$WORKING_DIRECTORY" || exit 1
}

# create s3 bucket
aws s3 mb "s3://$BUCKET_NAME"

# deploy lambda sources to s3
deploy_src "process_feed"
deploy_src "process_events"

# create or update infrastructure and application
terraform -chdir=terraform init
terraform -chdir=terraform apply\
  -var='versions={"process_feed":"'"$VERSION"'","process_events":"'"$VERSION"'"}'\
  -auto-approve
