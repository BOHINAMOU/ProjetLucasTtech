"""Compression gzip des réponses de l'API mobile uniquement (JSON : 4 à 8 fois plus léger sur le réseau).
Les pages HTML du site ne sont pas compressées ici (protection BREACH des jetons CSRF)."""
from django.middleware.gzip import GZipMiddleware


class ApiGZipMiddleware(GZipMiddleware):
    def process_response(self, request, response):
        if request.path.startswith('/api/'):
            return super().process_response(request, response)
        return response
