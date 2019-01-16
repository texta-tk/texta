import os

class BaseWorker:

    def run(self, task_id):
        raise NotImplementedError("Worker should implement run method")
    
    @staticmethod
    def create_file_path(filename, *args):
        '''
        Creates file path, eg for models/metadata/media.
        Params:
            filename - The name of the file
            args - Unpacked list of strings for directory of the file
        Example usage: 
            plot_url = self.create_file_path(plot_name, URL_PREFIX, MEDIA_URL, "task_manager", self.task_model_obj.task_type)
        '''

        dir_path = os.path.join(*args)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        full_path = os.path.join(dir_path, filename)

        return full_path

