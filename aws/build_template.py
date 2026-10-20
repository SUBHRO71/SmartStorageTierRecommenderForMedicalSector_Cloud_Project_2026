"""Generate the v2 CloudFormation template (JSON is also valid YAML)."""
import json
from pathlib import Path

def ref(name): return {"Ref": name}
def sub(value): return {"Fn::Sub": value}
def attr(name, key): return {"Fn::GetAtt": [name, key]}
resources = {}
def resource(name, kind, **properties):
    resources[name] = {"Type": "AWS::" + kind, "Properties": properties}
    return resources[name]

resource("ArchiveBucket", "S3::Bucket",
    BucketEncryption={"ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
    PublicAccessBlockConfiguration={k: True for k in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")},
    VersioningConfiguration={"Status": "Enabled"},
    LifecycleConfiguration={"Rules": [
        {"Id": tier, "Status": "Enabled", "Prefix": "studies/", "TagFilters": [{"Key": "tier", "Value": tier}],
         "Transitions": [{"StorageClass": tier, "TransitionInDays": days}]}
        for tier, days in [("STANDARD_IA", 30), ("GLACIER", 0), ("DEEP_ARCHIVE", 0)]] + [
        {"Id": "IncompleteUploads", "Status": "Enabled", "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}},
        {"Id": "OldCatalogBackups", "Status": "Enabled", "Prefix": "backups/", "ExpirationInDays": 30,
         "NoncurrentVersionExpiration": {"NoncurrentDays": 30}}]})
resources["ArchiveBucket"].update(DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
resource("ArchiveBucketPolicy", "S3::BucketPolicy", Bucket=ref("ArchiveBucket"), PolicyDocument={"Version": "2012-10-17", "Statement": [
    {"Effect": "Deny", "Principal": "*", "Action": "s3:*", "Resource": [attr("ArchiveBucket", "Arn"), sub("${ArchiveBucket.Arn}/*")],
     "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]})
resource("UserPool", "Cognito::UserPool", UserPoolName=sub("${AWS::StackName}-users"),
    AdminCreateUserConfig={"AllowAdminCreateUserOnly": True}, AliasAttributes=["email"], AutoVerifiedAttributes=["email"], UserPoolTier="LITE",
    Policies={"PasswordPolicy": {"MinimumLength": 14, "RequireLowercase": True, "RequireNumbers": True, "RequireSymbols": True, "RequireUppercase": True}})
resource("UserPoolClient", "Cognito::UserPoolClient", UserPoolId=ref("UserPool"), GenerateSecret=False,
    ExplicitAuthFlows=["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_ADMIN_USER_PASSWORD_AUTH"], PreventUserExistenceErrors="ENABLED",
    AccessTokenValidity=1, IdTokenValidity=1, RefreshTokenValidity=1)
for name, group in [("ViewerGroup", "viewer"), ("OperatorGroup", "operator"), ("AdminGroup", "archive-admin")]:
    resource(name, "Cognito::UserPoolGroup", GroupName=group, UserPoolId=ref("UserPool"))
resource("ServerRole", "IAM::Role", AssumeRolePolicyDocument={"Version": "2012-10-17", "Statement": [
    {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
    ManagedPolicyArns=[sub("arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore")],
    Policies=[{"PolicyName": "StudyArchive", "PolicyDocument": {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetBucketLocation"], "Resource": attr("ArchiveBucket", "Arn")},
        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:GetObjectTagging", "s3:PutObjectTagging", "s3:RestoreObject", "s3:AbortMultipartUpload"], "Resource": sub("${ArchiveBucket.Arn}/*")},
        {"Effect": "Allow", "Action": "s3:GetObject", "Resource": sub("arn:${AWS::Partition}:s3:::${ArtifactBucket}/releases/*")},
        {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"], "Resource": sub("arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/cloudtier-v2/*:*")}]}}])
resource("ServerProfile", "IAM::InstanceProfile", Roles=[ref("ServerRole")])
resource("ServerSecurityGroup", "EC2::SecurityGroup", GroupDescription="Only the Lambda gateway; administration through SSM", VpcId=ref("VpcId"),
    SecurityGroupIngress=[{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "SourceSecurityGroupId": ref("GatewaySecurityGroup")}],
    SecurityGroupEgress=[{"IpProtocol": "-1", "CidrIp": "0.0.0.0/0"}])
for name, path in [("BootstrapLog", "bootstrap"), ("NginxLog", "nginx")]:
    resource(name, "Logs::LogGroup", LogGroupName=f"/cloudtier-v2/{path}", RetentionInDays=14)
userdata = """#!/bin/bash
set -euo pipefail
mkdir -p /opt/cloudtier
aws s3 cp s3://${ArtifactBucket}/${ReleaseKey} /tmp/release.tgz --region ${AWS::Region}
tar -xzf /tmp/release.tgz -C /opt/cloudtier
cat > /etc/cloudtier.env <<'ENV'
AWS_DEFAULT_REGION=${AWS::Region}
ARCHIVE_BUCKET=${ArchiveBucket}
ARCHIVE_DB_PATH=/var/lib/cloudtier/archive.db
ARCHIVE_DATA_DIR=/var/lib/cloudtier/files
MRI_BUNDLE_DIR=/var/lib/cloudtier/model
COGNITO_USER_POOL_ID=${UserPool}
COGNITO_CLIENT_ID=${UserPoolClient}
FRONTEND_DIR=/opt/cloudtier/src/frontend/dist
HOME=/var/lib/cloudtier
OMP_NUM_THREADS=2
ENV
chmod 644 /etc/cloudtier.env
bash /opt/cloudtier/aws/bootstrap.sh
"""
resource("Server", "EC2::Instance", ImageId=ref("AmiId"), InstanceType=ref("InstanceType"), IamInstanceProfile=ref("ServerProfile"),
    MetadataOptions={"HttpTokens": "required", "HttpPutResponseHopLimit": 1},
    NetworkInterfaces=[{"DeviceIndex": "0", "AssociatePublicIpAddress": True, "SubnetId": ref("SubnetId"), "GroupSet": [ref("ServerSecurityGroup")]}],
    BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {"VolumeType": "gp3", "VolumeSize": 60, "Encrypted": True, "DeleteOnTermination": False}}],
    Tags=[{"Key": "Name", "Value": sub("${AWS::StackName}-study-server")}, {"Key": "Project", "Value": "CloudTierRecommender-v2"}],
    UserData={"Fn::Base64": sub(userdata)})["DependsOn"] = ["BootstrapLog", "NginxLog"]
resource("Alerts", "SNS::Topic")
resource("AlertSubscription", "SNS::Subscription", TopicArn=ref("Alerts"), Protocol="email", Endpoint=ref("NotificationEmail"))["Condition"] = "HasEmail"
resource("ServerAlarm", "CloudWatch::Alarm", AlarmDescription="Study server status check failed", Namespace="AWS/EC2", MetricName="StatusCheckFailed",
    Dimensions=[{"Name": "InstanceId", "Value": ref("Server")}], Statistic="Maximum", Period=60, EvaluationPeriods=2,
    Threshold=1, ComparisonOperator="GreaterThanOrEqualToThreshold", AlarmActions=[ref("Alerts")], TreatMissingData="notBreaching")
resource("MonthlyBudget", "Budgets::Budget", Budget={"BudgetName": sub("${AWS::StackName}-monthly"),
    "BudgetLimit": {"Amount": 100, "Unit": "USD"}, "TimeUnit": "MONTHLY", "BudgetType": "COST"},
    NotificationsWithSubscribers={"Fn::If": ["HasEmail", [{"Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 80, "ThresholdType": "PERCENTAGE"},
        "Subscribers": [{"SubscriptionType": "EMAIL", "Address": ref("NotificationEmail")}]}], ref("AWS::NoValue")]})

template = {"AWSTemplateFormatVersion": "2010-09-09", "Description": "CloudTier v2 study archive research pilot",
    "Parameters": {"VpcId": {"Type": "AWS::EC2::VPC::Id"}, "SubnetId": {"Type": "AWS::EC2::Subnet::Id"},
        "ArtifactBucket": {"Type": "String"}, "ReleaseKey": {"Type": "String"},
        "InstanceType": {"Type": "String", "Default": "m7i-flex.large", "AllowedValues": ["m7i-flex.large", "c7i-flex.large"]},
        "AmiId": {"Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>", "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"},
        "NotificationEmail": {"Type": "String", "Default": ""}},
    "Conditions": {"HasEmail": {"Fn::Not": [{"Fn::Equals": [ref("NotificationEmail"), ""]}]}}, "Resources": resources,
    "Outputs": {key: {"Value": value} for key, value in {

        "InstanceId": ref("Server"), "ArchiveBucketName": ref("ArchiveBucket"), "UserPoolId": ref("UserPool"),
        "UserPoolClientId": ref("UserPoolClient")}.items()}}
# Use the account-permitted Lambda HTTPS endpoint. CloudFront requires account verification.
resources["ArchiveBucket"]["Properties"]["CorsConfiguration"] = {"CorsRules": [{"AllowedOrigins": ["*"], "AllowedMethods": ["PUT", "HEAD"], "AllowedHeaders": ["content-type"], "MaxAge": 3600}]}
resources["ArchiveBucket"]["Properties"]["LifecycleConfiguration"]["Rules"].append({"Id": "StagedUploads", "Status": "Enabled", "Prefix": "staging/", "ExpirationInDays": 1, "NoncurrentVersionExpiration": {"NoncurrentDays": 1}})
resource("GatewaySecurityGroup", "EC2::SecurityGroup", GroupDescription="Lambda HTTPS gateway to study server", VpcId=ref("VpcId"), SecurityGroupEgress=[{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "CidrIp": "0.0.0.0/0"}])
resources["ServerSecurityGroup"]["Properties"]["SecurityGroupIngress"] = [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "SourceSecurityGroupId": ref("GatewaySecurityGroup")}]
resource("GatewayRole", "IAM::Role", AssumeRolePolicyDocument={"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}, ManagedPolicyArns=[sub("arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole")])
resource("Gateway", "Lambda::Function", Runtime="python3.12", Handler="index.handler", Role=attr("GatewayRole", "Arn"), Timeout=130, MemorySize=256, Code={"ZipFile": Path(__file__).with_name("https_gateway.py").read_text()}, Environment={"Variables": {"SERVER_IP": attr("Server", "PrivateIp")}}, VpcConfig={"SubnetIds": [ref("SubnetId")], "SecurityGroupIds": [ref("GatewaySecurityGroup")]})
resource("GatewayLog", "Logs::LogGroup", LogGroupName=sub("/aws/lambda/${Gateway}"), RetentionInDays=14)
resource("GatewayUrl", "Lambda::Url", TargetFunctionArn=attr("Gateway", "Arn"), AuthType="NONE", InvokeMode="BUFFERED")
resource("GatewayUrlPermission", "Lambda::Permission", FunctionName=ref("Gateway"), Action="lambda:InvokeFunctionUrl", Principal="*", FunctionUrlAuthType="NONE")
resource("GatewayInvokePermission", "Lambda::Permission", FunctionName=ref("Gateway"), Action="lambda:InvokeFunction", Principal="*", InvokedViaFunctionUrl=True)
template["Outputs"]["FrontendUrl"] = {"Value": attr("GatewayUrl", "FunctionUrl")}
template["Outputs"]["ApiUrl"] = {"Value": sub("${GatewayUrl.FunctionUrl}api")}
template["Outputs"]["GatewayFunctionName"] = {"Value": ref("Gateway")}
if __name__ == "__main__":
    Path(__file__).with_name("template.yaml").write_text(json.dumps(template, indent=2) + "\n")
