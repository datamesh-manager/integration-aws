# allow the process_events lambda to manage iam policies

data "aws_iam_policy_document" "process_events_iam_control" {
  statement {
    effect  = "Allow"
    actions = [
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "process_events_iam_control" {
  role   = aws_iam_role.process_events_iam_role.name
  policy = data.aws_iam_policy_document.process_events_iam_control.json
}
