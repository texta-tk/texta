from django.conf.urls import url

from . import views
from . import api_v1


urlpatterns = [
    # UI
    url(r'^$', views.index, name='index'),
    url(r'^start_task$', views.start_task, name='start_task'),
    url(r'^start_mass_task$', views.start_mass_task, name='start_mass_task'),
    url(r'^delete_task$', views.delete_task, name='delete_task'),
    url(r'download_model$', views.download_model, name='download_model'),

    # API
    url(r'^api/v1$', api_v1.api_info, name='api_info'),
    url(r'^api/v1/task_list$', api_v1.api_get_task_list, name='api_get_task_list'),
    url(r'^api/v1/task_status$', api_v1.api_get_task_status, name='api_get_task_status'),
    url(r'^api/v1/train_model$', api_v1.api_train_model, name='api_train_model'),
    url(r'^api/v1/train_tagger$', api_v1.api_train_tagger, name='api_train_tagger'),
    url(r'^api/v1/apply$', api_v1.api_apply, name='api_apply'),
    url(r'^api/v1/dataset_list$', api_v1.api_dataset_list, name='api_dataset_list'),
    url(r'^api/v1/search_list$', api_v1.api_search_list, name='api_search_list'),
    url(r'^api/v1/normalizer_list$', api_v1.api_normalizer_list, name='api_normalizer_list'),
    url(r'^api/v1/classifier_list$', api_v1.api_classifier_list, name='api_classifier_list'),
    url(r'^api/v1/reductor_list$', api_v1.api_reductor_list, name='api_reductor_list'),
    url(r'^api/v1/extractor_list$', api_v1.api_extractor_list, name='api_extractor_list'),
    url(r'^api/v1/tagger_list$', api_v1.api_tagger_list, name='api_tagger_list'),
    url(r'^api/v1/tag_list$', api_v1.api_tag_list, name='api_tag_list'),
    url(r'^api/v1/field_list$', api_v1.api_field_list, name='api_field_list'),
    url(r'^api/v1/mass_train_tagger$', api_v1.api_mass_train_tagger, name='api_mass_train_tagger'),
    url(r'^api/v1/mass_tagger$', api_v1.api_mass_tagger, name='api_mass_tagger'),
    url(r'^api/v1/tag_text$', api_v1.api_tag_text, name='api_tag_text'),
    url(r'^api/v1/tag_feedback$', api_v1.api_tag_feedback, name='api_tag_feedback'),
    url(r'^api/v1/document_tags_list$', api_v1.api_document_tags_list, name='api_document_tags_list'),
]
