# create lambda

resource "aws_lambda_function" "handle_events_lambda_function" {
  s3_bucket     = data.aws_s3_bucket.common_s3_bucket.bucket
  s3_key        = "handle_events/src/${var.versions.handle_events}/lambda.zip"
  function_name = "DMM_integration__handle_events"
  role          = aws_iam_role.handle_events_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 120
  runtime       = "python3.10"
  architectures = ["arm64"]

  environment {
    variables = {
      dmm_base_url                   = local.dmm_base_url
      dmm_api_key_secret_name        = local.dmm_api_key_secret_name
    }
  }
}

# trigger lambda on event in sqs

resource "aws_lambda_event_source_mapping" "handle_events_sqs_trigger" {
  event_source_arn = aws_sqs_queue.dmm_events_queue.arn
  function_name    = aws_lambda_function.handle_events_lambda_function.arn
}

# basic iam configuration to assume role

data "aws_iam_policy_document" "handle_events_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "handle_events_iam_role" {
  name               = "iam_for_handle_events_lambda"
  assume_role_policy = data.aws_iam_policy_document.handle_events_assume_role.json
}

# basic lambda execution role for log access

resource "aws_iam_role_policy_attachment" "handle_events_lambda_policy" {
  role       = aws_iam_role.handle_events_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
