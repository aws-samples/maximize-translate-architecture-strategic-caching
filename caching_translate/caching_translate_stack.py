from constructs import Construct
from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    aws_cognito as cognito, CfnOutput, RemovalPolicy
)
from .translation_cache import TranslationCache


class CachingTranslateStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        user_pool = cognito.UserPool(self, 'translate_cache_app_pool', self_sign_up_enabled=False,
                                     sign_in_aliases=cognito.SignInAliases(email=True))
        user_pool.apply_removal_policy(RemovalPolicy.DESTROY)

        CfnOutput(self, "UserPoolID", value=user_pool.user_pool_id)

        translate_only_scope = cognito.ResourceServerScope(scope_name="translate",
                                                           scope_description="Translate only access")
        resource_server = user_pool.add_resource_server("ResourceServer",
                                                        identifier="translate-cache",
                                                        scopes=[translate_only_scope]
                                                        )

        domain = user_pool.add_domain("CognitoDomain",
                                      cognito_domain=cognito.CognitoDomainOptions(
                                          domain_prefix=f"{construct_id}-{self.account}"
                                      )
                                      )

        client = user_pool.add_client("app-client",
                                      auth_flows=cognito.AuthFlow(admin_user_password=True, user_srp=True),
                                      o_auth=cognito.OAuthSettings(
                                          flows=cognito.OAuthFlows(
                                              authorization_code_grant=True,
                                              implicit_code_grant=True
                                          ),
                                          scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE,
                                                  cognito.OAuthScope.resource_server(resource_server,
                                                                                     translate_only_scope)],
                                          callback_urls=["https://localhost"]
                                      )
                                      )
        CfnOutput(self, "ClientID", value=client.user_pool_client_id)

        cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(self, 'TranslateCacheAuthorizer',
                                                              cognito_user_pools=[user_pool],
                                                              authorizer_name="TranslateCacheAuthorizer")

        translation_cache = TranslationCache(
            self, 'TranslationCache'
        )

        api = apigw.LambdaRestApi(
            self, 'translate_cache',
            handler=translation_cache._handler,
            proxy=False
        )
        items = api.root.add_resource("translate")
        items.add_method("POST", authorizer=cognito_authorizer, authorization_scopes=["translate-cache/translate"])

        CfnOutput(self, "APIGatewayName", value=api.rest_api_name)
        CfnOutput(self, "BaseURL", value=domain.base_url())
