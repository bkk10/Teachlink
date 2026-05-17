from teachly.wsgi import application

def handler(request):
    return application(request.environ, request.start_response)
