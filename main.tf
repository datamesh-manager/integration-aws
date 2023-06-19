variable "versions" {
  type = object({
    process_feed   = string
    process_events = string
  })
}

variable "aws" {
  type = object({
    region     = string
    access_key = string
    secret_key = string
  })
  sensitive = true
}

variable "dmm" {
  type = object({
    api_key = string
  })
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

resource "aws_iam_role" "process_feed_iam_role" {
  name               = "iam_for_process_feed_lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy_attachment" "process_feed_lambda_policy" {
  role       = aws_iam_role.process_feed_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "process_feed_lambda_function" {
  # todo: move lambda build versions to s3
  filename      = "${path.module}/out/process_feed_${var.versions.process_feed}.zip"
  function_name = "permissions__process_feed"
  role          = aws_iam_role.process_feed_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 60
  runtime       = "python3.10"
  architectures = ["arm64"]
}

resource "aws_secretsmanager_secret" "process_feed_dmm_api_key" {
  name                           = "process_feed_dmm_api_key"
  force_overwrite_replica_secret = true # make sure to override secret
  recovery_window_in_days        = 0 # force deletion on destroy
}

resource "aws_secretsmanager_secret_version" "dmm_api_key" {
  secret_id     = aws_secretsmanager_secret.process_feed_dmm_api_key.id
  secret_string = var.dmm.api_key
}

resource "aws_iam_role_policy" "sm_policy" {
  name = "process_feed_dmm_api_key_access"
  role = aws_iam_role.process_feed_iam_role.id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Effect   = "Allow"
        Resource = aws_secretsmanager_secret.process_feed_dmm_api_key.arn
      }
    ]
  })
}

resource "aws_s3_bucket" "permissions_bucket" {
  bucket        = "dmm-permissions-extension"
  force_destroy = true
}

data "aws_iam_policy_document" "process_feed_s3_access" {
  statement {
    principals {
      identifiers = [aws_iam_role.process_feed_iam_role.arn]
      type        = "AWS"
    }
    actions   = ["s3:GetObject", "s3:PutObject"]
    effect    = "Allow"
    resources = [
      aws_s3_bucket.permissions_bucket.arn,
      "${aws_s3_bucket.permissions_bucket.arn}/*"
    ]
  }
}

resource "aws_s3_bucket_policy" "process_feed_s3_access" {
  bucket = aws_s3_bucket.permissions_bucket.id
  policy = data.aws_iam_policy_document.process_feed_s3_access.json
}

resource "aws_sqs_queue" "dmm_events_queue" {
  name                        = "dmm-events.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60 # six times lambda timeout as stated in aws docs
}

data "aws_iam_policy_document" "process_feed_sqs_access" {
  statement {
    principals {
      identifiers = [aws_iam_role.process_feed_iam_role.arn]
      type        = "AWS"
    }
    actions   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
    effect    = "Allow"
    resources = [aws_sqs_queue.dmm_events_queue.arn]
  }
}

resource "aws_sqs_queue_policy" "process_feed_sqs_access" {
  queue_url = aws_sqs_queue.dmm_events_queue.id
  policy    = data.aws_iam_policy_document.process_feed_sqs_access.json
}


data "aws_iam_policy_document" "process_events_assume_role" { # todo rename process_events
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_lambda_function" "process_events_lambda_function" {
  # todo: move lambda build versions to s3
  filename      = "${path.module}/out/process_events_${var.versions.process_events}.zip"
  function_name = "permissions__process_events"
  role          = aws_iam_role.process_events_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 10
  runtime       = "python3.10"
  architectures = ["arm64"]
}


resource "aws_iam_role" "process_events_iam_role" {
  name               = "iam_for_process_events_lambda"
  assume_role_policy = data.aws_iam_policy_document.process_events_assume_role.json
}

data "aws_iam_policy_document" "process_events_sqs_access" {
  statement {
    principals {
      identifiers = [aws_iam_role.process_events_iam_role.arn]
      type        = "AWS"
    }
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    effect    = "Allow"
    resources = [aws_sqs_queue.dmm_events_queue.arn]
  }
}

resource "aws_sqs_queue_policy" "process_events_sqs_access" {
  queue_url = aws_sqs_queue.dmm_events_queue.id
  policy    = data.aws_iam_policy_document.process_events_sqs_access.json
}

resource "aws_iam_role_policy_attachment" "process_events_lambda_policy" {
  role       = aws_iam_role.process_events_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_event_source_mapping" "process_events_sqs_trigger" {
  event_source_arn = aws_sqs_queue.dmm_events_queue.arn
  function_name    = aws_lambda_function.process_events_lambda_function.arn
}
