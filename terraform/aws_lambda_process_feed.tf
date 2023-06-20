# create lambda

resource "aws_lambda_function" "process_feed_lambda_function" {
  # todo: move lambda build versions to s3
  filename      = "../out/process_feed_${var.versions.process_feed}.zip"
  function_name = "DMM_integration__process_feed"
  role          = aws_iam_role.process_feed_iam_role.arn
  handler       = "lambda_handler.lambda_handler"
  timeout       = 60
  runtime       = "python3.10"
  architectures = ["arm64"]
}

# todo trigger lambda periodically

# basic iam configuration to assume role

data "aws_iam_policy_document" "process_feed_assume_role" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "process_feed_iam_role" {
  name               = "iam_for_process_feed_lambda"
  assume_role_policy = data.aws_iam_policy_document.process_feed_assume_role.json
}

# basic lambda execution role for log access

resource "aws_iam_role_policy_attachment" "process_feed_lambda_policy" {
  role       = aws_iam_role.process_feed_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
