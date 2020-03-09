from itertools import zip_longest

from toolkit.core.project.models import Project
from toolkit.elastic.models import Index


def grouper(n, iterable, fillvalue=None):
    """
    Iterating trough an iterator/generator with chunks
    of size n.
    """
    container = []

    args = [iter(iterable)] * n
    chunks = zip_longest(fillvalue=fillvalue, *args)
    for chunk in chunks:
        chunk = [chunk for chunk in chunk if chunk is not None]
        container.append(chunk)

    return container[0]



def project_creation(project_title: str, index_title=None) -> Project:
    project = Project.objects.create(title=project_title)
    if index_title:
        index, is_created = Index.objects.get_or_create(name=index_title)
        project.indices.add(index)
    project.save()

    return project
