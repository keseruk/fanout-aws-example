import boto3
import json
import logging
from typing import Optional
from io import BytesIO
from PIL import Image

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.resource('s3')


def generate_thumbnail(bucket: str, key: str) -> Optional[BytesIO]:
    """
    Creates a thumbnail using the Python image library and returns it as a byte stream.

    :param bucket: The bucket that holds the source image.
    :param key: The object key in the bucket.
    :return: Returns a byte stream of the thumbnail.
    """
    client = boto3.client('s3')
    size = 200, 200
    stream = BytesIO()
    s3_object = client.get_object(Bucket=bucket, Key=key)['Body'].read()
    image = Image.open(BytesIO(s3_object))
    image.thumbnail(size, Image.ANTIALIAS)  # PIL keeps the aspect ratio
    image.save(stream, format=image.format)
    stream.seek(0)
    return stream


def upload_file(byte_stream: BytesIO, bucket: str, key: str) -> str:
    """
    Uploads a file from the given byte stream into S3.

    :param file_bytes: Image byte stream.
    :param bucket: The target bucket
    :param key: The object key in the bucket.
    :return: Returns the fully qualified S3 object path.
    """
    client = boto3.client('s3')
    res = client.put_object(Body=byte_stream, Bucket=bucket, Key=key)
    logging.info(f"Image uploaded to s3://{bucket}/{key}")
    return f"s3://{bucket}/{key}"


def handler(event, context):
    """
    Lambda handler function. Creates a thumbnail and uploads it to /processed/[FILENAME]/thumbnail_[FILENAME].jpg

    Batch processing is currently not supported.
    Make sure that the BatchSize is set to 1 in the function's SQS EventSourceMapping.

    :param event: The event from the SQS service
    :param context: Event context
    """
    if "Records" in event and len(event["Records"]) > 0:
        # process the first record only
        payload = event["Records"][0].get("body")
        json_payload = json.loads(payload)
        bucket = json_payload["Records"][0]["s3"]["bucket"]["name"]
        object_key = json_payload["Records"][0]["s3"]["object"]["key"]

        # the S3 notification filter should ensure that already processed objects won't be processed again
        # however I prefer adding a check to avoid endless processing
        if "processed" in object_key:
            return

        try:
            logging.info(f"Processing s3://{bucket}/{object_key}")
            thumbnail_bytes = generate_thumbnail(bucket, object_key)
            filename = object_key.split("/")[-1][:-4]
            if (thumbnail_bytes):
                upload_file(thumbnail_bytes, bucket, f"processed/{filename}/thumbnail_{filename}.jpg")

        except Exception as e:
            logging.exception(f"Failed to process s3://{bucket}/{object_key}")
            raise e
