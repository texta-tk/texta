import pathlib

from django.db import migrations

from toolkit.settings import RELATIVE_MODELS_PATH


def transfer_existing_cluster_paths(apps, schema_editor):
    """
    Function for translating full paths to model files to relative ones.
    """
    ClusteringResult = apps.get_model("topic_analyzer", "ClusteringResult")
    for cluster in ClusteringResult.objects.all():
        if cluster.vector_model:
            # Take only the file name without the source paths.
            file_name = pathlib.Path(cluster.vector_model.name).name
            new_path = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding" / file_name
            cluster.vector_model.name = str(new_path)

        cluster.save()


class Migration(migrations.Migration):
    dependencies = [
        ('topic_analyzer', '0002_add_embedding_and_sw_filter'),
    ]

    operations = [
        migrations.RunPython(transfer_existing_cluster_paths)
    ]
