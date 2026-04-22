############################
# GuardDuty
############################
resource "aws_guardduty_detector" "main" {
  enable = true
}

############################
# Security Hub
############################
resource "aws_securityhub_account" "main" {}

resource "aws_securityhub_standards_subscription" "aws_best_practices" {
  standards_arn = "arn:aws:securityhub:::standards/aws-foundational-security-best-practices/v/1.0.0"
}

############################
# SNS Topic
############################
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

############################
# IAM Role for Lambda
############################
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

############################
# IAM Policy (Least Privilege)
############################
resource "aws_iam_policy" "lambda_policy" {
  name = "${var.project_name}-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:CreateSecurityGroup",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:ModifyInstanceAttribute"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "securityhub:BatchImportFindings"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.alerts.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

############################
# Lambda Function
############################
resource "aws_lambda_function" "auto_response" {
  function_name = "${var.project_name}-lambda"
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  role          = aws_iam_role.lambda_role.arn

  filename         = "${path.module}/../lambda/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/lambda.zip")

  timeout = 30
}

############################
# EventBridge Rule
############################
resource "aws_cloudwatch_event_rule" "guardduty_rule" {
  name        = "${var.project_name}-rule"
  description = "Trigger Lambda on GuardDuty findings"

  event_pattern = jsonencode({
    source = ["aws.guardduty"],
    detail-type = ["GuardDuty Finding"]
  })
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.guardduty_rule.name
  target_id = "LambdaTarget"
  arn       = aws_lambda_function.auto_response.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_response.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.guardduty_rule.arn
}

############################
# API Gateway (Approval Endpoint)
############################
resource "aws_apigatewayv2_api" "approval_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id             = aws_apigatewayv2_api.approval_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.auto_response.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "approval_route" {
  api_id    = aws_apigatewayv2_api.approval_api.id
  route_key = "GET /approve"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.approval_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_response.function_name
  principal     = "apigateway.amazonaws.com"
}
