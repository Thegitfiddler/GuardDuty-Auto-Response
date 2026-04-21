import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")
ec2 = boto3.client("ec2")

SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:471112670973:SecurityAlerts"

API_URL = 'https://nntw4y1ri7.execute-api.us-east-1.amazonaws.com/prod/quarantine'

def lambda_handler(event, context):
    logger.info("Security Hub event received")
    logger.info(json.dumps(event))

    findings = event.get("detail", {}).get("findings", [])

    # Safety check
    if not findings:
        logger.info("No findings found in event")
        return {"statusCode": 200}

    for finding in findings:
        severity = finding["Severity"]["Label"].upper()
        logger.info(f"DEBUG → Severity Label: {severity}")

        resources = finding.get("Resources", [])

        instance_id = None
        for r in resources:
            if r.get("Type") == "AwsEc2Instance":
                instance_id = r.get("Id").split("/")[-1]

        logger.info(f"Instance ID: {instance_id}")

        # -----------------------------
        # LOW → Notify Only
        # -----------------------------
        if severity in ["LOW", "INFORMATIONAL"]:
            send_sns("LOW finding detected", instance_id, severity)

        # -----------------------------
        # MEDIUM → Tag + Notify
        # -----------------------------
        elif severity == "MEDIUM":
            if instance_id:
                tag_instance(instance_id)
            send_sns("MEDIUM finding - resource tagged", instance_id, severity)

        # -----------------------------
        # HIGH / CRITICAL → Approval Required
        # -----------------------------
        elif severity in ["HIGH", "CRITICAL"]:
            send_approval(instance_id, severity)

        else:
            logger.info(f"Unhandled severity: {severity}")

    return {"statusCode": 200}


# -----------------------------
# Tagging Function
# -----------------------------
def tag_instance(instance_id):
    try:
        ec2.create_tags(
            Resources=[instance_id],
            Tags=[{"Key": "SecurityStatus", "Value": "UnderInvestigation"}]
        )
        logger.info(f"Tagged instance {instance_id}")
    except Exception as e:
        logger.error(f"Tagging failed: {e}")


# -----------------------------
# SNS Notification
# -----------------------------
def send_sns(message, instance_id, severity):
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"Security Alert: {severity}",
            Message=f"{message}\nInstance: {instance_id}\nSeverity: {severity}"
        )
        logger.info("SNS notification sent")
    except Exception as e:
        logger.error(f"SNS failed: {e}")


# -----------------------------
# Approval Notification (HIGH)
# -----------------------------
def send_approval(instance_id, severity):
    try:
        approval_link = f"{API_URL}?instance_id={instance_id}"

        message = f"""
HIGH severity finding detected.

Instance: {instance_id}
Severity: {severity}

Click below to approve quarantine:
{approval_link}
"""

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="APPROVAL REQUIRED: Quarantine Instance",
            Message=message
        )

        logger.info("Approval notification sent")

    except Exception as e:
        logger.error(f"Approval SNS failed: {e}")
