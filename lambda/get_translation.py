import json
import os
import boto3
from generate_translations import generate_translations_with_cache
import time
from botocore.exceptions import ClientError

## Table structure
# ID | HASH (PK) | SRC_LANG | SRC_TEXT | TARGET_LANG | TARGET_TEXT
# table = ddb.Table(os.environ['TRANSLATION_CACHE_TABLE_NAME'])
_lambda = boto3.client('lambda')


def handler(event, context):

    print('request: {}'.format(json.dumps(event)))

    request = json.loads(event['body'])
    print("request", request)

    src_locale = request['src_locale']
    target_locale = request['target_locale']
    input_text = request['input_text']
    table_name = os.environ['TRANSLATION_CACHE_TABLE_NAME']

    if table_name == "":
        print("Defaulting table name")
        table_name = "TRANSLATION_CACHE"

    try:
        start = time.perf_counter()
        translations = generate_translations_with_cache(src_locale, target_locale, input_text, table_name)
        end = time.perf_counter()
        time_diff = (end - start)

        translations["processing_seconds"] = time_diff

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps(translations)
        }

    except ClientError as error:

        error = {"error_text": error.response['Error']['Code']}
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps(error)
        }


if __name__ == "__main__":
    print(handler(None, None))
