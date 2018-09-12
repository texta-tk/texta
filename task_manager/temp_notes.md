# Temporary notes for api_support branch

## Scheduler

```
python manage.py task-scheduler
```

cron example:

```
# Task Scheduler every 1 minute
*/1 * * * * python manage.py task-scheduler
```

## API sample

### Check API running
GET http://localhost:8000/task_manager/api/v1

### Task List
POST http://localhost:8000/task_manager/api/v1/task_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}

### Task Status
POST http://localhost:8000/task_manager/api/v1/task_status
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "task_id": 55
}

### Train Model
POST http://localhost:8000/task_manager/api/v1/train_model
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "min_freq": 10,
    "field": "field_value_en",
    "description": "API-test",
    "search": "all_docs",
    "dataset": 1,
    "num_dimensions": 100,
    "num_workers": 2
}

### Train Tagger
POST http://localhost:8000/task_manager/api/v1/train_tagger
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "normalizer_opt": "0",
    "classifier_opt": "0",
    "description": "API-A",
    "field": "field_value_en",
    "reductor_opt": "0",
    "dataset": 1,
    "search": "1",
    "extractor_opt": "0"
}

### Apply Preprocessor
POST http://localhost:8000/task_manager/api/v1/apply
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "text_tagger_taggers": ["6"],
    "search": "2",
    "text_tagger_feature_names": ["field_value_en"],
    "preprocessor_key": "text_tagger",
    "dataset": 1,
    "description": "API-T"
}
