import datetime
import boto3
import os
import base64

def handler(event, context):
    ec2 = boto3.client('ec2')

    # Fetch environment variables
    vpc_id = os.getenv("VPC_ID")
    security_group_id = os.getenv("SECURITY_GROUP_ID")
    router_ip = os.getenv("ROUTER_IP")
    ami_id = os.getenv("AMI_ID")
    key_name = os.getenv("KEY_NAME")
    subnet_id = os.getenv("SUBNET_ID")
    shard_instance_role_arn = os.getenv('ROLE_ARN')
    user_data = base64.b64decode(os.getenv("USER_DATA")).decode()
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    s3_object_name = os.getenv("OBJECT_KEY")

    unique_id = generate_unique_number()

    # Modify user data for this shard
    user_data = user_data.replace("%ROUTER_IP%", router_ip)
    user_data = user_data.replace("%S3_DOMAIN%", s3_bucket_name)
    user_data = user_data.replace("%OBJECT_KEY%", s3_object_name)
    user_data = user_data.replace("%UNIQUE_SHARD_NAME%", "shard" + str(unique_id) + "set")

    # Launch EC2 instance
    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="t2.micro",
        KeyName=key_name,
        SecurityGroupIds=[security_group_id],
        SubnetId=subnet_id, 
        MinCount=1,
        MaxCount=1,
        UserData=user_data,
        IamInstanceProfile={"Arn": shard_instance_role_arn},
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': 'MongoShardInstance' + str(unique_id)}
                ]
            },
        ]
    )

    instance_id = response['Instances'][0]['InstanceId']
    return {"InstanceId": instance_id}

def generate_unique_number():
        """
        Generates a unique number based on the current datetime up to seconds.
        The format is YYYYMMDDHHMMSS (year, month, day, hour, minute, second).
        """
        now = datetime.datetime.now()
        unique_number = int(now.strftime("%Y%m%d%H%M%S"))
        return unique_number
