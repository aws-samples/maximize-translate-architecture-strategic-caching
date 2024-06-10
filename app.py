import aws_cdk as cdk

from caching_translate.caching_translate_stack import CachingTranslateStack

app = cdk.App()

CachingTranslateStack(app, "caching-translate", env=cdk.Environment(account='xxxxxxxxxxxx', region='xxxxxxx'))

app.synth()
