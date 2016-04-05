from django.http import HttpResponseRedirect
import settings

def HTTPS_ResponseRedirect(request,url):
    if settings.SERVER_TYPE == "DEV":
        new_url = url
    else:
        absolute_url = request.build_absolute_uri(url)
        new_url = "https%s" % absolute_url[4:]
    return HttpResponseRedirect(new_url)
