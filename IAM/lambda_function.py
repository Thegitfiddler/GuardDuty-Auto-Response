import boto3
import json
import logging
import datetime

# This sets up a logger so we can see what's happening in CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# -------------------------------------------------------
# ENTRY POINT — Lambda starts here every time it's triggered
# -------------------------------------------------------
def lambda_handler(event, context):
    logger.info("GuardDuty finding received.")
    logger.info(json.dumps(event))  # Log the full event for learning purposes

    # Step 1: Read the finding details
    detail      = event.get("detail", {})
    finding_id  = detail.get("id", "unknown")
    severity    = detail.get("severity", 0)
    description = detail.get("description", "No description provided")

    logger.info(f"Finding ID: {finding_id} | Severity: {severity}")

    # Step 2: Only act on HIGH severity (7.0 or above)
    if severity >= 7.0:
        logger.info("HIGH severity detected — starting incident response.")

        # Step 3: Find which EC2 instance is affected
        instance_id = get_instance_id(detail)

        # Step 4: Isolate it if we found one
        if instance_id:
            isolate_ec2_instance(instance_id)
        else:
            logger.info("No EC2 instance found in this finding. Skipping isolation.")

        # Step 5: Log the incident everywhere
        send_alert(finding_id, severity, description, instance_id)

    else:
        logger.info(f"Severity {severity} is below threshold. No action taken.")

    return {"statusCode": 200, "body": "Done"}


# -------------------------------------------------------
# FUNCTION 1 — Dig into the finding to get the instance ID
# -------------------------------------------------------
def get_instance_id(detail):
    try:
        instance_id = (
            detail
            .get("resource", {})
            .get("instanceDetails", {})
            .get("instanceId")
        )
        if instance_id:
            logger.info(f"Affected instance found: {instance_id}")
        return instance_id
    except Exception as e:
        logger.error(f"Error getting instance ID: {e}")
        return None


# -------------------------------------------------------
# FUNCTION 2 — Isolate the compromised EC2 instance
# -------------------------------------------------------
def isolate_ec2_instance(instance_id):
    ec2 = boto3.client("ec2")

    try:
        # Find the VPC this instance lives in
        response = ec2.describe_instances(InstanceIds=[instance_id])
        vpc_id   = response["Reservations"][0]["Instances"][0]["VpcId"]
        logger.info(f"Instance lives in VPC: {vpc_id}")

        # Create a quarantine security group (empty = no traffic allowed)
        sg_response = ec2.create_security_group(
            GroupName   = f"QUARANTINE-{instance_id}",
            Description = "Auto-quarantine: blocks all traffic to/from this instance",
            VpcId       = vpc_id
        )
        quarantine_sg_id = sg_response["GroupId"]
        logger.info(f"Quarantine security group created: {quarantine_sg_id}")

        # Remove the default outbound rule (deny all outbound too)
        ec2.revoke_security_group_egress(
            GroupId       = quarantine_sg_id,
            IpPermissions = [{
                "IpProtocol" : "-1",
                "IpRanges"   : [{"CidrIp": "0.0.0.0/0"}]
            }]
        )

        # Attach the quarantine group to the instance (replaces existing SGs)
        ec2.modify_instance_attribute(
            InstanceId = instance_id,
            Groups     = [quarantine_sg_id]
        )
        logger.info(f"SUCCESS: Instance {instance_id} has been isolated.")

    except Exception as e:
        logger.error(f"Failed to isolate instance {instance_id}: {e}")


# -------------------------------------------------------
# FUNCTION 3 — Send alerts to CloudWatch and Security Hub
# -------------------------------------------------------
def send_alert(finding_id, severity, description, instance_id):

    # CloudWatch gets the log automatically — this just makes it obvious
    logger.warning(
        f"INCIDENT RESPONSE COMPLETE | "
        f"Finding: {finding_id} | "
        f"Severity: {severity} | "
        f"Instance Isolated: {instance_id} | "
        f"Details: {description}"
    )

    # Post a custom finding to Security Hub
    hub      = boto3.client("securityhub")
    sts      = boto3.client("sts")
    account  = sts.get_caller_identity()["Account"]
    now      = datetime.datetime.utcnow().isoformat() + "Z"

    try:
        hub.batch_import_findings(Findings=[{
            "SchemaVersion" : "2018-10-08",
            "Id"            : f"auto-response-{finding_id}",
            "ProductArn"    : f"arn:aws:securityhub:us-east-1:{account}:product/{account}/default",
            "GeneratorId"   : "lambda-auto-response",
            "AwsAccountId"  : account,
            "CreatedAt"     : now,
            "UpdatedAt"     : now,
            "Title"         : "Automated Incident Response Executed",
            "Description"   : f"Lambda isolated instance {instance_id} in response to GuardDuty finding {finding_id}.",
            "Severity"      : {"Label": "HIGH"},
            "Types"         : ["Software and Configuration Checks"],
            "Resources"     : [{
                "Type" : "AwsEc2Instance",
                "Id"   : instance_id or "unknown"
            }]
        }])
        logger.info("Security Hub alert posted successfully.")

    except Exception as e:
        logger.error(f"Could not post to Security Hub: {e}")