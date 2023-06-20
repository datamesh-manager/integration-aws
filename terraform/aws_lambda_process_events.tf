# create lambda

resource "aws_lambda_function" "process_events_lambda_function" {
  # todo: move lambda build versions to s3
  filename      = "../out/process_events_${var.versions.process_events}.zip"
  function_name = "DMM_integration__process_events"
  role          = aws_iam_role.process_events_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 10
  runtime       = "python3.10"
  architectures = ["arm64"]
}

# trigger lambda on event in sqs

resource "aws_lambda_event_source_mapping" "process_events_sqs_trigger" {
  event_source_arn = aws_sqs_queue.dmm_events_queue.arn
  function_name    = aws_lambda_function.process_events_lambda_function.arn
}

# basic iam configuration to assume role

data "aws_iam_policy_document" "process_events_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "process_events_iam_role" {
  name               = "iam_for_process_events_lambda"
  assume_role_policy = data.aws_iam_policy_document.process_events_assume_role.json
}

# basic lambda execution role for log access

resource "aws_iam_role_policy_attachment" "process_events_lambda_policy" {
  role       = aws_iam_role.process_events_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}