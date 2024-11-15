import aws_cdk as core
import aws_cdk.assertions as assertions

from mongodb_sharding_cdk.mongodb_sharding_cdk_stack import MongodbShardingCdkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in mongodb_sharding_cdk/mongodb_sharding_cdk_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MongodbShardingCdkStack(app, "mongodb-sharding-cdk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
