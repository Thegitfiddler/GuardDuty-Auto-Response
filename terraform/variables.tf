variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "guardduty-auto-response"
}

variable "alert_email" {
  description = "Email for SNS notifications"
  type        = string
}
