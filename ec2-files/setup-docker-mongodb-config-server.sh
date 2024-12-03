#!/bin/bash

# Update the system
sudo yum update -y

# Install Docker
sudo yum install -y docker amazon-cloudwatch-agent

# Start Docker service and enable it to start on boot
sudo systemctl start docker
sudo systemctl enable docker

# Add the EC2 default user to the docker group for permission to run Docker commands
sudo usermod -aG docker ec2-user

# Install Docker Compose (v2 integrated with Docker CLI)
DOCKER_COMPOSE_BIN="/usr/local/bin/docker-compose"
if ! docker compose version >/dev/null 2>&1; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o $DOCKER_COMPOSE_BIN
    sudo chmod +x $DOCKER_COMPOSE_BIN
fi

# Verify installation of Docker and Docker Compose
docker --version
docker-compose version

aws s3 cp s3://%S3_DOMAIN%/%OBJECT_KEY% /home/ec2-user/docker-compose.yml
aws s3 cp s3://%S3_MONITORING_JSON_DOMAIN%/%MONITORING_JSON_KEY% /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
cd /home/ec2-user
mkdir mongoLogs
chmod 777 ./mongoLogs/

docker-compose up -d

# Check if the MongoDB config server is ready
echo "Waiting for mongo-config-server to be ready..."
until docker exec mongo-config-server mongosh --eval "db.runCommand({ ping: 1 })" --port 27019 > /dev/null 2>&1; do
    echo "Waiting for mongo-config-server to accept connections..."
    sleep 2
done


# Generate IMDSv2 token with a TTL of 300 seconds (5 minutes)
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")

# Get the public IP address using the token
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)

echo $PUBLIC_IP

# Check if PUBLIC_IP is empty
if [ -z "$PUBLIC_IP" ]; then
    echo "Failed to retrieve public IP from metadata service."
    exit 1
fi

# Initialize the replica set for the config server
echo "Initializing replica set for mongo-config-server..."
docker exec mongo-config-server mongosh --eval "rs.initiate(
    {
        _id: 'configReplSet',
        configsvr: true,
        members: [
            { _id: 0, host: '${PUBLIC_IP}:27019' }
        ]
    }
)" --port 27019

sudo /opt/aws/amazon-cloudwatch-agent/bin/start-amazon-cloudwatch-agent