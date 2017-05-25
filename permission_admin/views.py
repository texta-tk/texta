import datetime
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User, Group, Permission
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from permission_admin.models import Dataset
from utils.es_manager import ES_Manager
from texta.settings import STATIC_URL, URL_PREFIX


@login_required
@user_passes_test(lambda u: u.is_superuser)
def add_dataset(request):
    daterange = ""
    Dataset(author=request.user, index=request.POST['index'], mapping=request.POST['mapping'], daterange=daterange).save()
    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_dataset(request):
    index_to_delete = request.POST['index']
    index_to_delete = Dataset.objects.get(pk = index_to_delete)
    index_to_delete.delete()
    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def open_close_dataset(request):
    dataset_id = request.POST['dataset_id']
    dataset = Dataset.objects.get(pk = dataset_id)

    if request.POST['open_close'] == 'open':
        ES_Manager.open_index(dataset.index)
    else:
        ES_Manager.close_index(dataset.index)
    
    return HttpResponse()
    


@login_required
@user_passes_test(lambda u: u.is_superuser)
def index(request):
    indices = ES_Manager.get_indices()
    datasets = get_datasets(indices=indices)
    users = User.objects.all()
    
    template = loader.get_template('permission_admin.html')
    return HttpResponse(template.render({'users':users,'datasets':datasets,'indices':indices,'STATIC_URL':STATIC_URL,'URL_PREFIX':URL_PREFIX},request))

def get_datasets(indices=None):
    datasets = Dataset.objects.all()
    datasets_out = []
    for dataset in datasets:
        ds_out = dataset.__dict__
        if indices:
            for index in indices:
                if index['index'] == ds_out['index']:
                    ds_out['status'] = index['status']
                    ds_out['docs_count'] = index['docs_count']
                    ds_out['store_size'] = index['store_size']
        datasets_out.append(ds_out)
    return datasets


@login_required
@user_passes_test(lambda u: u.is_superuser)
def change_isactive(request):
    user_id = request.POST['user_id']
    change = request.POST['change']

    if change == 'activate':
        is_active = True
    else:
        is_active = False

    user = User.objects.get(pk=int(user_id))
    user.is_active = is_active
    user.save()
    
    return HttpResponse()    


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_user(request):
    user_id_to_delete = request.POST['user_id']
    user_to_delete = User.objects.get(pk = user_id_to_delete)
    user_to_delete.delete()
    return HttpResponseRedirect(URL_PREFIX + '/permission_admin/')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def change_permissions(request):
    user_id = request.POST['user_id']
    change = request.POST['change']

    if change == 'to_superuser':
        is_superuser = True
    else:
        is_superuser = False

    user = User.objects.get(pk=int(user_id))
    user.is_superuser = is_superuser
    user.save()    
        
    return HttpResponse() 

@login_required
@user_passes_test(lambda u: u.is_superuser)
def get_mappings(request):
    index = request.GET['index']
    return HttpResponse(json.dumps(ES_Manager.get_mappings(index)))




