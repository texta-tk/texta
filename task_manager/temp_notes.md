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
```
GET http://localhost:8000/task_manager/api/v1
```

### Task List
```
POST http://localhost:8000/task_manager/api/v1/task_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}
```

### Task Status
```
POST http://localhost:8000/task_manager/api/v1/task_status
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "task_id": 55
}
```

### Train Model
```
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
```

### Train Tagger
```
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
```

### Apply Preprocessor
```
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
```


### List Valid Datasets
```
POST http://localhost:8000/task_manager/api/v1/dataset_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}
```

### List Valid Searches
```
POST http://localhost:8000/task_manager/api/v1/search_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1
}
```

### List Valid Normalizers
```
POST http://localhost:8000/task_manager/api/v1/normalizer_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}
```

### List Valid Classifiers
```
POST http://localhost:8000/task_manager/api/v1/classifier_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}
```

### List Valid Reductor
```
POST http://localhost:8000/task_manager/api/v1/reductor_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}
```

### List Valid Extractor
```
POST http://localhost:8000/task_manager/api/v1/extractor_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc"
}
```

### List Unique Tags
```
POST http://localhost:8000/task_manager/api/v1/tag_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1
}
```

### List Unique Fields
```
POST http://localhost:8000/task_manager/api/v1/field_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1
}
```

### Mass Trainer
```
POST http://localhost:8000/task_manager/api/v1/mass_train_tagger
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1,

    "tags": ["A"],              // Optional
    "field": "field_value_en",  // Optional
    "normalizer_opt": "0",      // Optional
    "classifier_opt": "0",      // Optional
    "reductor_opt": "0",        // Optional
    "extractor_opt": "0"        // Optional
}
```

### Mass Tagger
```
POST http://localhost:8000/task_manager/api/v1/mass_tagger
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1,
    "search": 1,                // Optional
    "field": "field_value_en",
    "taggers": ["14"]
}
```

### Hybrid Tagger
```
POST http://localhost:8000/task_manager/api/v1/hybrid_tagger
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1,
    "search": 1,
    "max_taggers": 10,              // Optional
    "min_count_threshold": 50,      // Optional
    "field": "field_value_en"
}
```

### Apply Tagger Text
```
POST http://localhost:8000/task_manager/api/v1/tag_text
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "text": "Maybe I can reply to them by e-mail.",
    "taggers": [4, 7]              // Optional
}
```

### Get Document Tags
```
POST http://localhost:8000/task_manager/api/v1/document_tags_list
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1,
    "document_ids": ["GYtrE2QB28-0KXnd6zcj"]
}
```

### Feedback
```
POST http://localhost:8000/task_manager/api/v1/tag_feedback
Content-Type: application/json

{
    "auth_token": "60aa4ecb8aa5fc",
    "dataset": 1,
    "field": "field_value_en",
    "document_ids": ["GYtrE2QB28-0KXnd6zcj"], 
    "tag": "A",
    "value": 1
}
```
