from constructs import Construct
from aws_cdk import (
    aws_lambda as _lambda,
    aws_dynamodb as ddb,
    aws_iam as _iam,
    RemovalPolicy as RemovalPolicy

)


class TranslationCache(Construct):

    @property
    def handler(self):
        return self._handler

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        table = ddb.Table(
            self, 'TRANSLATION_CACHE',
            table_name='TRANSLATION_CACHE',
            partition_key={'name': 'hash', 'type': ddb.AttributeType.STRING},
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="purge_date"
        )

        self._handler = _lambda.Function(
            self, 'GetTranslationHandler',
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler='get_translation.handler',
            code=_lambda.Code.from_asset('lambda'),
            environment={
                'TRANSLATION_CACHE_TABLE_NAME': table.table_name,
            }
        )

        lambda_translate_access = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW,
            actions=["translate:TranslateText"],
            resources=["*"]
        )

        self._handler.add_to_role_policy(lambda_translate_access)

        table.grant_read_write_data(self._handler)
