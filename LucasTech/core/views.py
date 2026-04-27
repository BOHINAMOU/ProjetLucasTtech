from django.shortcuts import render
from django.http import HttpResponse
def home(request):
    return render(request, 'core/base.html')
# Create your views here.
from .models import Partner

def partners(request):
    return {
        'partners': Partner.objects.all()
    }