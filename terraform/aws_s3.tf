# create s3 bucket

data "aws_s3_bucket" "common_s3_bucket" {
  bucket = "dmm-integration"
}

# enable versioning

resource "aws_s3_bucket_versioning" "versioning_example" {
  bucket = data.aws_s3_bucket.common_s3_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
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
    resources = ["${data.aws_s3_bucket.common_s3_bucket.arn}/process_feed/last_event_id"]
  }
}

resource "aws_s3_bucket_policy" "process_feed_s3_access" {
  bucket = data.aws_s3_bucket.common_s3_bucket.id
  policy = data.aws_iam_policy_document.process_feed_s3_access.json
}
