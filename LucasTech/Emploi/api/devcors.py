"""CORS réservé au développement : permet à l'aperçu web de l'application mobile (localhost:8081) d'appeler l'API locale.
Ce middleware n'est ajouté que lorsque DEBUG est vrai (voir settings.py) : il n'existe pas en production."""
from django.http import HttpResponse


class DevCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        response = HttpResponse(status=204) if request.method == 'OPTIONS' else self.get_response(request)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'authorization, content-type, accept'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, DELETE, OPTIONS'
        return response
