import sys

def apply_celery_task(task_func, *args):
    if not 'test' in sys.argv:
        task_func.apply_async(args=(*args,))
    else:
        task_func.apply(args=(*args,))

def get_payload(request):
    # if request.GET:
    #     data = request.GET
    # elif request.POST:
    #     data = request.data
    # else:
    #     data = {}
    
    # request.GET or request.POST only works with formdata, not json data
    return request.data
