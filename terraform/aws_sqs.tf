# create queue for forwarded DMM events in sqs

resource "aws_sqs_queue" "dmm_events_queue" {
  name                        = var.event_queue_name
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60 # six times the consuming lambda timeout as stated in aws docs
}

# give access to DMM event queue to lambdas

data "aws_iam_policy_document" "lambda_sqs_access" {
  statement {
    principals {
      identifiers = [aws_iam_role.poll_feed_iam_role.arn]
      type        = "AWS"
    }
    actions   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
    effect    = "Allow"
    resources = [aws_sqs_queue.dmm_events_queue.arn]
  }

  statement {
    principals {
      identifiers = [aws_iam_role.manage_iam_policies_iam_role.arn]
      type        = "AWS"
    }
    effect    = "Allow"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.dmm_events_queue.arn]
  }
}

resource "aws_sqs_queue_policy" "lambda_sqs_access" {
  queue_url = aws_sqs_queue.dmm_events_queue.id
  policy    = data.aws_iam_policy_document.lambda_sqs_access.json
}
