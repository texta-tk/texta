from multiprocessing import Process
from time import sleep
import json
import sys


class Syncer(Process):
    """Synchronizes datasets with their source by rerunning the whole importation process. Already processed documents
    are identified by the index and left unprocessed.
    """

    def __init__(self, dataset_imports, importer, interval=60):
        super(Syncer, self).__init__()

        self._dataset_import = dataset_imports
        self._importer = importer
        self._interval = interval

    def run(self):
        """An eternal loop which runs all the reimport jobs at an interval.
        """
        while True:
            try:
                try:
                    self._import_missing_data()
                    self._write_heartbeat('All synced')
                except Exception as exception:
                    self._write_heartbeat(str(exception))
                sleep(self._interval)
            except:
                sys.exit(0)  # Avoid Process Syncer-1: KeyboardInterrupt message at TEXTA termination

    def _write_heartbeat(self, message):
        pass

    def _import_missing_data(self):
        for dataset_import in self._dataset_import.objects.filter(must_sync=True):
            self._sync_dataset(dataset_import=dataset_import)

    def _sync_dataset(self, dataset_import):
        import_parameters = json.loads(dataset_import.json_parameters)
        self._importer.reimport(parameters=import_parameters)