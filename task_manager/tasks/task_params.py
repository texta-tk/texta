
from .language_model import LanguageModel
from .taggin_model import TaggingModel


task_params = [
	{
		"name":            "Train Language Model",
		"id":              "train_model",
		"template":        "task_parameters/train_model.html",
		"model":           LanguageModel(),
		"allowed_actions": ["delete", "save"]
	},
	{
		"name":            "Train Text Tagger",
		"id":              "train_tagger",
		"template":        "task_parameters/train_tagger.html",
		"model":           TaggingModel(),
		"allowed_actions": ["delete", "save"]
	},
	{
		"name":            "Apply preprocessor",
		"id":              "apply_preprocessor",
		"template":        "task_parameters/apply_preprocessor.html",
		"allowed_actions": []
	}
]
