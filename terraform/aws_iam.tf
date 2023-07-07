# allow the handle_events lambda to manage iam policies

data "aws_iam_policy_document" "handle_events_iam_control" {
  statement {
    effect  = "Allow"
    actions = [
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "handle_events_iam_control" {
  role   = aws_iam_role.handle_events_iam_role.name
  policy = data.aws_iam_policy_document.handle_events_iam_control.json
}
