#!/bin/bash

aws s3 rb --force "s3://dmm-integration"
terraform -chdir=terraform destroy\
  -var='versions={"poll_feed":"0","manage_iam_policies":"0"}'\
  -auto-approve
