from django.urls import path

from toolkit.document_importer.views import DocumentImportView, DocumentInstanceView, UpdateSplitDocument


document_import_urls = [
    path('projects/<int:pk>/elastic/documents/', DocumentImportView.as_view(), name="document_import"),
    path('projects/<int:pk>/elastic/documents/<str:index>/<str:document_id>/', DocumentInstanceView.as_view(), name="document_instance"),
    path('projects/<int:pk>/elastic/documents/<str:index>/update_split', UpdateSplitDocument.as_view(), name="update_split_document"),
]
