import base64
import datetime
import os
from aws_cdk import (
    Duration,
    aws_s3_assets as s3_assets,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as _lambda,
    CfnOutput,
    Stack,
)

from constructs import Construct

class MongodbShardingCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        file_base_path = os.path.dirname(__file__)
        mongo_router_config_init_script_path = os.path.join(file_base_path, "../ec2-files/setup-docker-mongodb-config-server.sh")
        mongo_shard_config_init_script_path = os.path.join(file_base_path, "../ec2-files/setup-shard-server.sh")
        docker_compose_config_server_file_path  = os.path.join(file_base_path, "../ec2-files/config-router-docker-compose.yml")
        docker_compose_shard_server_file_path  = os.path.join(file_base_path, "../ec2-files/shard-server-docker-compose.yml")
        monitor_config_file_path  = os.path.join(file_base_path, "../ec2-files/amazon-cloudwatch-agent.json")
        
        # VPC for the MongoDB setup
        vpc = ec2.Vpc(self, "MongoDBVPC", max_azs=2)

        security_group = ec2.SecurityGroup(self, "MongoDBSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True
        )

        security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(27017), "Allow MongoDB router")
        security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(27018), "Allow MongoDB shard")
        security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(27019), "Allow MongoDB config server")
        security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "Allow SSH from public access")

        # IAM Role for EC2 Instances
        instance_role = iam.Role(
            self,
            "MongoDBInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
            ],
        )

        # S3 assets
        docker_compose_config_server_asset = s3_assets.Asset(self, "DockerComposeMongoConfigAsset",
            path=docker_compose_config_server_file_path)

        docker_compose_shard_server_asset = s3_assets.Asset(self,   "DockerComposeMongoShardAsset",
            path=docker_compose_shard_server_file_path)
        
        cloudwatch_config_asset = s3_assets.Asset(self,   "CloudwatchConfigAsset",
            path=monitor_config_file_path)


        # Amazon Linux image
        machine_image = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023
        )

        # MongoDB Router and Config Server Instance
        router_instance = ec2.Instance(
                            self,
                            "MongoRouterInstance",
                            instance_type=ec2.InstanceType("t2.micro"),
                            machine_image=machine_image,
                            vpc=vpc,
                            role=instance_role,
                            security_group=security_group,
                            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                            associate_public_ip_address=True,
                            key_name="mongodb-router-key",
                            require_imdsv2=True
                        )
        
        router_instance.node.add_dependency(docker_compose_config_server_asset)
        router_instance.node.add_dependency(cloudwatch_config_asset)

        # User data script to install Docker and set up MongoDB router and config server
        with open(mongo_router_config_init_script_path, "r") as userdata_file:
            user_data = userdata_file.read()
        
        router_instance.add_user_data(user_data
                                        .replace("%S3_DOMAIN%", docker_compose_config_server_asset.s3_bucket_name)
                                        .replace("%OBJECT_KEY%", docker_compose_config_server_asset.s3_object_key)
                                        .replace("%S3_MONITORING_JSON_DOMAIN%", cloudwatch_config_asset.s3_bucket_name)
                                        .replace("%MONITORING_JSON_KEY%", cloudwatch_config_asset.s3_object_key)
                                      )


        docker_compose_config_server_asset.grant_read(router_instance.role)

        # MongoDB Router and Config Server Instance
        monitoring_instance = ec2.Instance(
                            self,
                            "MongoMonitoringInstance",
                            instance_type=ec2.InstanceType("t2.micro"),
                            machine_image=machine_image,
                            vpc=vpc,
                            role=instance_role,
                            security_group=security_group,
                            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                            associate_public_ip_address=True,
                            key_name="mongodb-router-key",
                            require_imdsv2=True
                        )
        

        # Output Router's Public IP
        self.router_ip_output = router_instance.instance_public_ip

        shard_id = self.generate_unique_number()

        # MongoDB Router and Config Server Instance
        initial_shard_instance = ec2.Instance(
                            self,
                            "MongoShardInstance-" + str(shard_id),
                            instance_type=ec2.InstanceType("t2.micro"),
                            machine_image=machine_image,
                            vpc=vpc,
                            role=instance_role,
                            security_group=security_group,
                            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                            associate_public_ip_address=True,
                            key_name="mongodb-router-key",
                        )
        
        docker_compose_shard_server_asset.grant_read(initial_shard_instance.role)

        with open(mongo_shard_config_init_script_path, "r") as userdata_file:
            user_data = userdata_file.read()

        initial_shard_instance.add_user_data(user_data
                                        .replace("%S3_DOMAIN%", docker_compose_shard_server_asset.s3_bucket_name)
                                        .replace("%OBJECT_KEY%", docker_compose_shard_server_asset.s3_object_key)
                                        .replace("%ROUTER_IP%", self.router_ip_output)
                                        .replace(
                                            "%UNIQUE_SHARD_NAME%", "shard" + str(shard_id) + "set"
                                        )
                                      )

        self.export_router_ip()
        vpc_id = vpc.vpc_id
        security_group_id = security_group.security_group_id


        # Lambda Role
        lambda_role = iam.Role(
            self, "MongoDBScalingLambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2FullAccess"),
            ],
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[instance_role.role_arn]
            )
        )


        lambda_role.node.add_dependency(instance_role)

        public_subnet = vpc.public_subnets[0]

        # Lambda Function to add shards dynamically
        add_shard_lambda = _lambda.Function(
            self, "AddShardFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="add_shard.handler",
            timeout=Duration.minutes(15),
            code=_lambda.Code.from_asset("lambda"),
            environment={
                "VPC_ID": vpc_id,
                "SECURITY_GROUP_ID": security_group_id,
                "ROUTER_IP": self.router_ip_output,
                "KEY_NAME": "mongodb-router-key",
                "AMI_ID": machine_image.get_image(self).image_id,
                "USER_DATA": base64.b64encode(user_data.encode()).decode(),
                "SUBNET_ID": public_subnet.subnet_id,
                "S3_BUCKET_NAME": docker_compose_shard_server_asset.s3_bucket_name,
                "OBJECT_KEY": docker_compose_shard_server_asset.s3_object_key,
                "ROLE_ARN": instance_role.role_arn
            },
            role=lambda_role,
        )

        add_shard_lambda.node.add_dependency(instance_role)


    def generate_unique_number(self):
        """
        Generates a unique number based on the current datetime up to seconds.
        The format is YYYYMMDDHHMMSS (year, month, day, hour, minute, second).
        """
        now = datetime.datetime.now()
        unique_number = int(now.strftime("%Y%m%d%H%M%S"))
        return unique_number
    
    def export_router_ip(self):
        """
        Output the public IP of the router instance as a CloudFormation export.
        """
        CfnOutput(
            self, "MongoRouterPublicIP",
            value=self.router_ip_output,
            export_name="MongoRouterPublicIP"
        )