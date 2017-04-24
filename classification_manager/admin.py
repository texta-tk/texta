from django.contrib import admin
from .models import ModelClassification

#from myproject.admin_site import custom_admin_site

#@admin.register(Author, Reader, Editor, site=custom_admin_site)
#class PersonAdmin(admin.ModelAdmin):
    #pass
    
@admin.register(ModelClassification)
class ModelRunManager(admin.ModelAdmin):
    pass

# if custom __init__, then
# admin.site.register(ModelRun,ModelRunManager)