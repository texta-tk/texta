from time import sleep
import requests
import logging

class MLPTaskAdapter(object):

    def __init__(self, mlp_url, mlp_type='mlp'):
        self.start_task_url = '{0}/task/start/{1}'.format(mlp_url.strip('/'), mlp_type)
    
    def process(self, data):
        errors = {}
        current_fail_count = 0
        status_code = 500

        while status_code == 500:
            started_task = requests.post(self.start_task_url, data=data)
            current_status_code = int(started_task.status_code)

            if current_status_code == 500:
                current_fail_count += 1
                if current_fail_count > 3:
                    task_status_text = 'FAILURE'
                    status_code = 666
                    break
            else:
                status_code = current_status_code
                task_status_text = 'PENDING'
                current_fail_count = 0

        while task_status_text == 'PENDING':
            sleep(10)
            try:
                task_status = requests.get(started_task['url']).json()
                task_status_text = task_status['status']
                current_fail_count = 0
            except:
                current_fail_count += 1
                # if fail to fetch result 3 times, declare task failed
                if current_fail_count > 3:
                    task_status_text = 'FAILURE'
                    logging.error('Task failed because correct response not sent from MLP')
                else:
                    logging.error('Failed to parse MLP response. Trying again ({})...'.format(current_fail_count))

        analyzation_data = []

        if task_status_text == 'FAILURE':
            errors = {'task_failed': task_status}
            logging.error('Failed to analyze text with MLP Lite', extra={'url':self.start_task_url, 'texts': json.dumps(texts, ensure_ascii=False)})
        elif task_status_text == 'SUCCESS':
            analyzation_data = task_status['result']
        
        return analyzation_data, errors
