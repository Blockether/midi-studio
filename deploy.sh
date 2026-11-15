#!/usr/bin/env bash
# Deploy MIDI Studio to AWS Lambda: the image, then the stack.
# The script is safe to run again. It deploys the files of this directory.
#
#   ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

STACK=${STACK:-midi-studio}
REGION=${AWS_REGION:-eu-central-1}
ENGINE=${ENGINE:-docker}
export AWS_REGION=$REGION AWS_DEFAULT_REGION=$REGION AWS_PAGER=

account=$(aws sts get-caller-identity --query Account --output text)
registry=$account.dkr.ecr.$REGION.amazonaws.com

echo "1/2 image"
aws ecr describe-repositories --repository-names "$STACK" >/dev/null 2>&1 ||
  aws ecr create-repository --repository-name "$STACK" --image-scanning-configuration scanOnPush=true >/dev/null
# Each run pushes one image. ECR keeps the 5 newest images and removes the others.
aws ecr put-lifecycle-policy --repository-name "$STACK" --lifecycle-policy-text '{"rules":[{"rulePriority":1,
  "description":"Keep the 5 newest images","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":5},
  "action":{"type":"expire"}}]}' >/dev/null
aws ecr get-login-password | "$ENGINE" login --username AWS --password-stdin "$registry" >/dev/null
tag=$(date -u +%Y%m%d%H%M%S)
"$ENGINE" build --platform linux/arm64 --tag "$registry/$STACK:$tag" .
# Lambda needs the Docker image format, not the OCI format with attestations.
if [ "$ENGINE" = podman ]; then
  podman push --format docker "$registry/$STACK:$tag"
else
  docker push "$registry/$STACK:$tag"
fi
digest=$(aws ecr describe-images --repository-name "$STACK" --image-ids imageTag="$tag" --query 'imageDetails[0].imageDigest' --output text)

echo "2/2 stack $STACK"
aws cloudformation deploy --stack-name "$STACK" --template-file template.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides "Image=$registry/$STACK@$digest" --no-fail-on-empty-changeset
aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].Outputs[?OutputKey==`Url`].OutputValue' --output text
