from openai.error import InvalidRequestError

a = InvalidRequestError(message='The model `gpt-4` does not exist or you do not have access to it. Learn more: https://help.openai.com/en/articles/7102672-how-can-i-access-gpt-4.', param=None, code='model_not_found', http_status=404)
print(a._message)