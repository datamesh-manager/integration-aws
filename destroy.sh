#!/bin/bash

aws s3 rb --force "s3://dmm-integration"
terraform -chdir=terraform destroy -var='versions={"process_feed":"0","process_events":"0"}' -auto-approve
