# GuardDuty Automated Incident Response

An automated cloud security pipeline built on AWS that detects 
threats and isolates compromised resources within seconds — 
without any manual intervention.

---

## Project Overview

This project simulates a real-world Security Operations Center (SOC) 
automated response workflow using native AWS security services.

When Amazon GuardDuty detects a HIGH severity threat, this pipeline
automatically:
1. Identifies the affected EC2 instance
2. Creates a quarantine security group (no inbound/outbound traffic)
3. Attaches it to the compromised instance, cutting off all access
4. Logs the full incident to CloudWatch
5. Posts a structured finding to AWS Security Hub

**Response time: under 10 seconds from detection to isolation.**

---

## Architecture

GuardDuty (detects threat)
↓
EventBridge (routes finding)
↓
Lambda (executes response)
↓           ↓           ↓
Isolate EC2   CloudWatch   Security Hub
(quarantine)   (logs)      (findings)

---

## AWS Services Used

| Service | Role in Project |
|---|---|
| Amazon GuardDuty | Threat detection and finding generation |
| AWS Lambda | Automated response logic (Python 3.12) |
| Amazon EventBridge | Event routing from GuardDuty to Lambda |
| Amazon EC2 | Target resource being protected/isolated |
| AWS Security Hub | Centralized security findings dashboard |
| Amazon CloudWatch | Execution logs and audit trail |
| AWS IAM | Least privilege access control |

---

## Security Practices

### Least Privilege IAM
The Lambda execution role is granted only the exact permissions 
required. Broad managed policies are intentionally avoided.

| Permission | Reason |
|---|---|
| ec2:DescribeInstances | Identify the VPC of the affected instance |
| ec2:CreateSecurityGroup | Create an isolated quarantine group |
| ec2:RevokeSecurityGroupEgress | Remove all outbound rules |
| ec2:ModifyInstanceAttribute | Attach quarantine group to instance |
| securityhub:BatchImportFindings | Report incident to Security Hub |
| sts:GetCallerIdentity | Retrieve account ID for ARN construction |
| logs:CreateLogGroup/Stream/PutLogEvents | Write execution logs |

CloudWatch access is scoped to this function's log group only.

### No Hardcoded Credentials
All AWS API calls use the Lambda execution role via IAM. 
No access keys or secrets exist anywhere in this codebase.

### Sensitive Data Excluded
A `.gitignore` is configured to prevent credentials, `.env` files, 
and key files from ever being committed.

---

## How to Deploy

### Prerequisites
- An AWS account
- AWS Console access
- GuardDuty and Security Hub enabled in us-east-1

### Steps
1. Enable GuardDuty in your AWS account
2. Enable Security Hub and connect GuardDuty as a data source
3. Create a Lambda function (Python 3.12) and paste `lambda/lambda_function.py`
4. Attach the IAM policy in `iam/least_privilege_policy.json` to the Lambda role
5. Create an EventBridge rule using the pattern in `eventbridge/event_pattern.json`
6. Set the EventBridge target to your Lambda function
7. Test using GuardDuty → Settings → Generate sample findings

---

## Testing

GuardDuty includes a built-in sample findings generator.

1. Go to GuardDuty → Settings → Generate sample findings
2. Navigate to CloudWatch → Log groups → `/aws/lambda/GuardDutyAutoResponse`
3. Confirm logs show isolation executed for HIGH severity findings
4. Navigate to Security Hub → Findings to confirm the report was posted

---

## Screenshots

| Step | Screenshot |
|---|---|
| GuardDuty enabled | Screenshots/GuardDuty.png |
| Lambda function deployed | ![Lambda](screenshots/02_lambda_function.png) |
| EventBridge rule configured | ![EventBridge](screenshots/03_eventbridge_rule.png) |
| CloudWatch logs showing isolation | ![CloudWatch](screenshots/04_cloudwatch_logs.png) |
| Security Hub finding posted | ![Security Hub](screenshots/05_security_hub_finding.png) |
| IAM least privilege policy | ![IAM](screenshots/06_iam_policy.png) |

---

## What I Learned

- How AWS-native security services connect to form a detection pipeline
- Event-driven architecture using EventBridge and Lambda
- IAM least privilege design and why it matters
- Automated incident response patterns used in real SOC environments
- How to isolate compromised cloud resources programmatically

---

## Author

Michael Jones  
Aspiring Security/Detection Engineer  
