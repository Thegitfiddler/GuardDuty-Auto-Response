output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.approval_api.api_endpoint
}
