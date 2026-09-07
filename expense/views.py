from django.http import JsonResponse


def home(request):
    return JsonResponse({"detail": "The interface has moved to the Next.js frontend."}, status=410)
