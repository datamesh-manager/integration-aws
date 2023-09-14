# create secret for data mesh manager in secretsmanager

resource "aws_secretsmanager_secret" "dmm_api_key" {
  name                           = local.dmm_api_key_secret_name
  force_overwrite_replica_secret = true # make sure to override secret
  recovery_window_in_days        = 0    # force deletion on destroy
}

resource "aws_secretsmanager_secret_version" "dmm_api_key" {
  secret_id     = aws_secretsmanager_secret.dmm_api_key.id
  secret_string = var.dmm.api_key
}

# give secrets manager access to lambdas for the data mesh manager api key

data "aws_iam_policy_document" "lambda_secretsmanager_access" {
  statement {
    principals {
      identifiers = [
        aws_iam_role.poll_feed_iam_role.arn,
        aws_iam_role.manage_iam_policies_iam_role.arn
      ]
      type = "AWS"
    }
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.dmm_api_key.arn]
  }
}

resource "aws_secretsmanager_secret_policy" "lambda_secretsmanager_access" {
  secret_arn = aws_secretsmanager_secret.dmm_api_key.arn
  policy     = data.aws_iam_policy_document.lambda_secretsmanager_access.json
}
