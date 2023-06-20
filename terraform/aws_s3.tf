# create s3 bucket

resource "aws_s3_bucket" "bucket" {
  bucket        = "dmm-integration"
  force_destroy = true
}

# give access to s3 bucket to process_feed lambda to keep state of latest event id

data "aws_iam_policy_document" "process_feed_s3_access" {
  statement {
    principals {
      identifiers = [aws_iam_role.process_feed_iam_role.arn]
      type        = "AWS"
    }
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.bucket.arn}/process_feed/last_event_id"]
  }
}

resource "aws_s3_bucket_policy" "process_feed_s3_access" {
  bucket = aws_s3_bucket.bucket.id
  policy = data.aws_iam_policy_document.process_feed_s3_access.json
}
