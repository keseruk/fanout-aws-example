import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def copy_with_metadata(bucket: str, object_key: str, labels: dict):
    """
    Makes a copy of the image with labels added as metadata
    For example, cat123.jpg is copied to processed/cat123/cat123_original.jpg

    :param bucket: S3 bucket name
    :param object_key: S3 object key
    :param labels: Key-value pairs to be added as object meta
    """
    tags = "&".join([f"{key}={value}" for key, value in labels.items()])

    s3 = boto3.resource("s3")
    filename = object_key.split("/")[-1][:-4]
    s3.Object(bucket, f"processed/{filename}/{filename}_original.jpg").copy_from(
        CopySource={'Bucket': bucket, 'Key': object_key}, Tagging=tags, TaggingDirective="REPLACE")


def get_labels(bucket: str, object_key: str, num_labels: int = 5) -> dict:
    """
    Get labels from the Amazon Rekognition service.

    :param bucket: The S3 bucket name
    :param object_key: The S3 object name
    :param num_labels: The number of labels to be returned
    :return: Returns the list of 
    """
    client = boto3.client("rekognition", region_name="eu-central-1")
    logging.info(f"Detecting labels of {object_key} in bucket: {bucket}")

    response = client.detect_labels(Image={"S3Object": {"Bucket": bucket, "Name": object_key}},
                                    MinConfidence=50, MaxLabels=num_labels)

    labels = {}
    for label in response["Labels"]:
        labels[label.get("Name")] = str(label.get("Confidence"))

    return labels


def handler(event, context):
    """
    Lambda handler function.

    :param event: The event from the SQS service
    :param context: Event context
    """
    if "Records" in event and len(event["Records"]) > 0:

        payload = event["Records"][0].get("body")
        json_payload = json.loads(payload)
        bucket = json_payload["Records"][0]["s3"]["bucket"]["name"]
        object_key = json_payload["Records"][0]["s3"]["object"]["key"]

        if "processed" in object_key:
            return

        try:
            labels = get_labels(bucket, object_key)
            copy_with_metadata(bucket, object_key, labels)
        except Exception as e:
            logging.exception(f"Failed to process s3://{bucket}/{object_key}")
            raise e
