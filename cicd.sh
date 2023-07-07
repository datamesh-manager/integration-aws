#!/bin/bash

if [ -z "$1" ]; then
  echo "Please set version!"
  exit 0
fi

VERSION=$1
WORKING_DIRECTORY=$(pwd)
BUCKET_NAME="dmm-integration"

declare -a LAMBDAS=("poll_feed" "handle_events")

function build {
  local name=$1
  local src="src/$name"
  local out="out/$name"

  # clean
  rm -rf "$out"
  mkdir -p "$out"

  # copy sources
  cp -r "$src/lambda_handler.py" "$src/requirements.txt" "$out"
  cd "$out" || exit 1

  # install dependencies
  python3.10 -m pip install --upgrade -r requirements.txt --target .

  cd "$WORKING_DIRECTORY" || exit 1
}

function test {
  local name=$1
  local src="src/$name"
  local out="out/$name"

  # copy testfile
  cp -r "$src/test_lambda_handler.py" "$out"
  cd "$out" || exit 1

  # run tests
  python3.10 -m unittest -v test_lambda_handler -f
  exit_code=$?

  # exit if any test failed
  if [ $exit_code != 0 ]; then exit $exit_code
  fi

  # remove testfile
  rm test_lambda_handler.py

  cd "$WORKING_DIRECTORY" || exit 1
}

function deploy {
  local name=$1
  local result="${name}_${VERSION}.zip"

  cd "out/$name" || exit 1

  # bundle
  zip -rqu "$result" .

  # copy to s3
  aws s3 cp "$result" "s3://$BUCKET_NAME/$name/src/${VERSION}/lambda.zip"

  # back to working directory
  cd "$WORKING_DIRECTORY" || exit 1
}

# create s3 bucket
aws s3 mb "s3://$BUCKET_NAME"

# build lambda sources
for i in "${LAMBDAS[@]}" ; do
  build "$i"
done

# test lambda sources
for i in "${LAMBDAS[@]}" ; do
  test "$i"
done

# deploy lambda sources to s3
for i in "${LAMBDAS[@]}" ; do
  deploy "$i"
done

# create or update infrastructure and application
terraform -chdir=terraform init -upgrade
terraform -chdir=terraform apply\
  -var='versions={"poll_feed":"'"$VERSION"'","handle_events":"'"$VERSION"'"}'\
  -auto-approve
