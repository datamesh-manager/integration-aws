# create lambda

resource "aws_lambda_function" "poll_feed_lambda_function" {
  s3_bucket     = data.aws_s3_bucket.common_s3_bucket.bucket
  s3_key        = "poll_feed/src/${var.versions.poll_feed}/lambda.zip"
  function_name = "DMM_integration__poll_feed"
  role          = aws_iam_role.poll_feed_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 59
  runtime       = "python3.10"
  architectures = ["arm64"]

  environment {
    variables = {
      bucket_name               = var.bucket_name
      dmm_base_url              = local.dmm_base_url
      dmm_api_key_secret_name   = local.dmm_api_key_secret_name
      last_event_id_object_name = local.last_event_id_object_name
      sqs_queue_url             = aws_sqs_queue.dmm_events_queue.url
    }
  }
}

# trigger poll feed lambda every minute

resource "aws_cloudwatch_event_rule" "poll_feed_schedule" {
  name                = "schedule_dmm_poll_feed"
  description         = "Schedule for Lambda Function"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "poll_feed_schedule_target" {
  rule      = aws_cloudwatch_event_rule.poll_feed_schedule.name
  target_id = "poll_feed_lambda"
  arn       = aws_lambda_function.poll_feed_lambda_function.arn
}


resource "aws_lambda_permission" "poll_feed_schedule_permission" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.poll_feed_lambda_function.function_name
  principal     = "events.amazonaws.com"
}

# basic iam configuration to assume role

data "aws_iam_policy_document" "poll_feed_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "poll_feed_iam_role" {
  name               = "iam_for_poll_feed_lambda"
  assume_role_policy = data.aws_iam_policy_document.poll_feed_assume_role.json
}

# basic lambda execution role for log access

resource "aws_iam_role_policy_attachment" "poll_feed_lambda_policy" {
  role       = aws_iam_role.poll_feed_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
