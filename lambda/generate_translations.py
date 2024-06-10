from datetime import datetime, timedelta

from botocore.config import Config
from botocore.exceptions import ClientError
import boto3
import hashlib

import time


def does_target_language_exists(target_language):
    """Checks whether the requested target language exists.

    Args:
        target_language: Target language.

    """

    supported_languages = get_supported_target_languages()

    exists_count = supported_languages.count(target_language)

    if exists_count > 0:
        return True
    else:
        return False


def get_supported_target_languages():
    """Returns all languages that Amazon Translate supports.

    Returns:
        A list of language codes. For example:

        ['es', 'fr']
    """

    translate = boto3.client('translate', use_ssl=True)

    response = translate.list_languages()

    language_codes = []

    for language in response['Languages']:
        language_codes.append(language['LanguageCode'])

    print(len(language_codes))
    return language_codes


def get_hash_from_text(text):
    """Calculates and returns an MD5 hash of the input text.

    Args:
        text: Input text

    Returns:
        An sha256 hash in hexadecimal representation.
    """
    sha256_hash = hashlib.sha256(text.encode())

    # sha256_hash.update(text)
    print(sha256_hash.hexdigest())

    return sha256_hash.hexdigest()


def should_cache_be_used(input, table_name):
    """Checks whether the translation is cached in the DynamoDb table.

    Args:
        input: The input object.
        table_name: Name of the table where the cache is stored.

    Returns:
        A tuple containing, in this order, whether cache is to be used and output
        object containing the database details if object is cached. If cache
        is not used then the calculated hash is returned.
    """

    dynamodb = boto3.resource("dynamodb")

    # Calculate the sha256 hash of the original messages file.
    translation_key = input['src_locale'] + "-" + input['target_locale'] + "-" + input['src_text']
    current_hash = get_hash_from_text(translation_key)

    table = dynamodb.Table(table_name)  # ID | HASH (PK) | SRC_LOCALE | SRC_TEXT | TARGET_LOCALE | TARGET_TEXT

    # Get the hash of the messages file from the cache bucket.
    use_cache = False
    output = {}
    try:

        response = table.get_item(
            Key={
                'hash': current_hash
            }
        )
        print(response)

        if 'Item' in response:
            #print("Retrieved messages file from cache", json.dumps(response['Item']))
            use_cache = True
            print('Hashes match, will try to use cache first')
            output["hash"] = response['Item']["hash"]
            output["translated_text"] = response['Item']["translated_text"]
            output["src_text"] = response['Item']["src_text"]
            output["src_locale"] = response['Item']["src_locale"]
            output["target_locale"] = response['Item']["target_locale"]
        else:
            use_cache = False
            output["hash"] = current_hash
            print('Hashes do not match, cache will be skipped')

    except ClientError as e:
        print("Error-" + e.response)

    return use_cache, output


def translate_language(input):
    """Translate the input text from and to the specified languages by
    invoking the Amazon Translate API.


    Args:
        input: Contains following attributes
        src_locale: The ISO code of the language to translate from, e.g., 'en'.
        target_locale: The ISO code of the language to translate to, e.g., 'es'.
        text: the text to be translated.
    """
    print("Translating from '{}' to '{}'".format(input['src_locale'], input['target_locale']))

    try:
        config = Config(
            retries={
                'max_attempts': 10,
                'mode': 'standard'
            }
        )
        translate = boto3.client('translate', use_ssl=True, config=config)

        response = translate.translate_text(
            Text=input['src_text'],
            SourceLanguageCode=input['src_locale'],
            TargetLanguageCode=input['target_locale']
        )

    except ClientError as error:
        raise error

    return response['TranslatedText']


def cache_translated_text(input, table_name, current_hash):
    """This method caches the translated cache when there is a cache miss

        Args:
            input: Contains following attributes
                src_locale: The ISO code of the language to translate from, e.g., 'en'.
                target_locale: The ISO code of the language to translate to, e.g., 'es'.
                text: the text to be translated.
                translated_text: Translated Text
            table_name: Dynamodb table storing cached translations
            current_hash: The MD5 hash of the current text to be stored in the DynamoDB table

        """
    dynamodb = boto3.resource('dynamodb')

    table = dynamodb.Table(table_name)

    # translation_key = input['src_locale'] + "-" + input['target_locale'] + "-" + input['src_text']
    # current_hash = get_hash_from_text(translation_key)

    now = datetime.now()
    one_month_later = now + timedelta(days=1)
    epoch_time = int(one_month_later.timestamp())

    try:
        response = table.put_item(
            Item={
                'hash': current_hash,
                'src_locale': input['src_locale'],
                'target_locale': input['target_locale'],
                'src_text': input['src_text'],
                'translated_text': input['translated_text'],
                'purge_date': epoch_time
            }
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("PutItem succeeded:")
        #print(json.dumps(response, indent=4))


def generate_translations_with_cache(src_locale, target_locale, input_text, table_name):
    """Translate the app to all applicable languages and use teh cache if it exists

    Args:
        src_locale: Input src language
        target_locale: Target language to be converted the input text in.
        input_text: Input text to be translated
        table_name: Dynamodb table storing cached translations

    """
    # Split the text into multiple sentences

    statement_tokens = input_text.split(".")

    translated_text_list = []

    use_cache = False

    input = {'src_locale': src_locale, 'target_locale': target_locale}

    for statement in statement_tokens:
        # Determine whether we should try to get translations from the cache first.
        # This will save us requests to the Amazon Translate API. input['src_locale'] + "-" + input['target_locale'] + "-" + input['src_text']

        if statement == '':
            continue

        input[
            'src_text'] = statement + "."  # adding the . back since w/o . Translate automaically in some cases adds a . to statements.

        use_cache, output = should_cache_be_used(input, table_name)

        if use_cache:
            #print("Retrieved messages file from cache", json.dumps(output))
            translated_text_list.append(output["translated_text"])

        else:
            translated_text = translate_language(input)
            translated_text_list.append(translated_text)
            input['translated_text'] = translated_text
            cache_translated_text(input, table_name, output["hash"])

    translations = {"translated_text": "".join(translated_text_list), "cached_result": use_cache}
    print(translations)
    return translations
