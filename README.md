# MongoDB Sharding AWS CDK Project

This project leverages AWS CDK with Python to deploy infrastructure required for setting up a dynamic MongoDB sharding cluster on AWS. The project includes EC2 instances for MongoDB shard servers, router, and config servers, a Lambda function for creating additional EC2 instances dynamically, and other essential configurations.

## Project Structure

The project is organized as follows:

- **ec2-files/**: Contains files for deploying and configuring the MongoDB sharded cluster.
  - **config-router-docker-compose.yml**: Docker Compose file to deploy router, and config server of MongoDB.
  - **shard-server-docker-compose.yml**: Docker Compose file to deploy shard server of MongoDB.
  - **setup-docker-mongodb-config-server.sh**: Shell scripts to initialize EC2 instances for router and config.
  - **setup-shard-server.sh**: Shell scripts to initialize EC2 instances for shard server.
  - **amazon-cloudwatch-agent.json**: Configuration file for CloudWatch monitoring.

- **lambda/**: Contains code for an AWS Lambda function that creates new EC2 instances.

- **data-loader.ipynb**: Jupyter Notebook used to add data to the started MongoDB cluster. After deploying the cluster, use the displayed IP address in this notebook to add data and make multiple queries for dynamic sharding.

## Prerequisite Setup

Before running this project, ensure you have the following prerequisites installed and set up:

1. **Create an AWS Account**: If you don't have an AWS account, you can create one at [https://aws.amazon.com/](https://aws.amazon.com/). Follow the instructions provided to set up your account.

2. **Configure AWS CLI**: Once you have an AWS account, install AWS CLI on your local machine if you haven't already [Refer this link to install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). Then generate IAM User for AWS CLI with **AdministratorAccess** policy [Refer this article](https://medium.com/@sam.xzo.developing/create-aws-iam-user-02ee9c65c877).Then, configure access ID and Key to AWS CLI:
    ```
    aws configure
    ```
    Follow the prompts to enter your Access Key ID, Secret Access Key, default region `'us-east-2'`, and output format. These credentials should belong to an IAM user with administrative access created previously.


3. **Node.js**: Install Node.js from [https://nodejs.org/](https://nodejs.org/) if you haven't already. This project requires Node.js for running scripts and managing dependencies.

4. **AWS CDK**: Install AWS Cloud Development Kit (CDK) for TypeScript globally using npm by running the following command:
    ```
    npm install -g typescript aws-cdk
    ```

5. **Bootstrap CDK (First-Time Setup)**: If this is your first time using AWS CDK in your AWS account, you need to bootstrap your environment. Run the following command:
    ```
    cdk bootstrap
    ```
## Setup Instructions

**Create Virtual Environment:**

- On MacOS and Linux:
  ```bash
  python3 -m venv .venv

- On Windows:
    ```bash
    python -m venv .venv
    ```

**Activate Virtual Environment:**
- On MacOS and Linux:
    ```bash
    source .venv/bin/activate
- On Windows:
    ```bash
    .venv\Scripts\activate.bat
    ```

**Install Dependencies:**
```bash
.venv\Scripts\activate.bat
```
    

**Synthesize CloudFormation Template:**
```bash
cdk synth
```

**Deploy the Stack:**
- Deploy the infrastructure using the following command:
    ```bash
    cdk deploy
    ```

**Load Data into MongoDB Cluster:**

After deployment, use the IP address provided by the stack in data-loader.ipynb to connect and load data into the MongoDB cluster. Then connect Router IP address and execute multiple quries to trigger new instance creation.