variable "aws" {
  type = object({
    region     = string
    access_key = string
    secret_key = string
  })
  sensitive = true
}


terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.56"
    }
  }
}

provider "aws" {
  region     = var.aws.region
  access_key = var.aws.access_key
  secret_key = var.aws.secret_key
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  name               = "iam_for_lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_lambda_function" "process_feed_lambda_function" {
  filename      = "${path.module}/out/process_feed/process_feed.zip"
  function_name = "permissions__process_feed"
  role          = aws_iam_role.iam_for_lambda.arn
  handler       = "process_feed.lambda_handler"

  runtime       = "python3.10"
  architectures = ["arm64"]
}
