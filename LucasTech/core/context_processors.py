from .models import Partner

def partners(request):
    return {
        'partners': Partner.objects.all()
    }