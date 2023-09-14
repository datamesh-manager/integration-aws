# create lambda

resource "aws_lambda_function" "manage_iam_policies_lambda_function" {
  s3_bucket     = data.aws_s3_bucket.common_s3_bucket.bucket
  s3_key        = "manage_iam_policies/src/${var.versions.manage_iam_policies}/lambda.zip"
  function_name = "DMM_integration__manage_iam_policies"
  role          = aws_iam_role.manage_iam_policies_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 30
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

resource "aws_lambda_event_source_mapping" "manage_iam_policies_sqs_trigger" {
  event_source_arn = aws_sqs_queue.dmm_events_queue.arn
  function_name    = aws_lambda_function.manage_iam_policies_lambda_function.arn
}

# basic iam configuration to assume role

data "aws_iam_policy_document" "manage_iam_policies_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "manage_iam_policies_iam_role" {
  name               = "iam_for_manage_iam_policies_lambda"
  assume_role_policy = data.aws_iam_policy_document.manage_iam_policies_assume_role.json
}

# basic lambda execution role for log access

resource "aws_iam_role_policy_attachment" "manage_iam_policies_lambda_policy" {
  role       = aws_iam_role.manage_iam_policies_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
