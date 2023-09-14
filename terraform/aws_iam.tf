# allow the manage_iam_policies lambda to manage iam policies

data "aws_iam_policy_document" "manage_iam_policies_iam_control" {
  statement {
    effect  = "Allow"
    actions = [
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "manage_iam_policies_iam_control" {
  role   = aws_iam_role.manage_iam_policies_iam_role.name
  policy = data.aws_iam_policy_document.manage_iam_policies_iam_control.json
}
