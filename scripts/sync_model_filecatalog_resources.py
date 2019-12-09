import pathlib
import json
from toolkit.neurotagger.models import Neurotagger
from toolkit.tagger.models import *


# This is a script to purge all models and images on the filesystem
# that are not referenced inside the database in case there is a fault
# in the resource deletion or they get out of sync for whatever reason.

# Do note that iterating through an Model.objects.all() slams the database
# with queries so this script is not suited for constant periodic use but rather
# during specific scenarios where it is necessary.


# Containers for keeping all the paths that are stored in the database.
django_models = set()
django_plots = set()

# Get all the paths of the existing files, glob fetches all files that match the wildcard pattern.
file_models = set(str(path) for path in pathlib.Path("/var/texta-rest/data/models/tagger").glob("*"))
file_plots = set(str(path) for path in pathlib.Path("/var/texta-rest/data/media/").glob("*"))

# For every TaggerGroups tagger, add their path to the container.
tagger_groups = TaggerGroup.objects.all()
for tagger_group in tagger_groups:
    taggers = tagger_group.taggers.all()
    for tagger in taggers:
        if tagger.location and tagger.plot:
            model_path = json.loads(tagger.location)["tagger"]
            django_models.add(model_path)
            django_plots.add(tagger.plot.path)

# Add neurotagger plots to the container.
neuroplots = set(str(neurotagger.plot.path) for neurotagger in Neurotagger.objects.all())
django_plots.update(neuroplots)

# From the files distract the paths that are inside a Django model to get the hanging ones.
hanging_plots = file_plots - django_plots
hanging_models = file_models - django_models

# Delete all the hanging files.
for path in hanging_models:
    pathlib.Path(path).unlink()

for path in hanging_plots:
    pathlib.Path(path).unlink()
