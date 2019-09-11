from .settings import BASE_DIR
import os

# Path to the log directory. Default is /log
LOG_PATH = os.path.join(BASE_DIR, "data", "log")



# Paths to info and error log files.
INFO_LOG_FILE_NAME = os.path.join(LOG_PATH, "info.log")
ERROR_LOG_FILE_NAME = os.path.join(LOG_PATH, "error.log")

# Logger IDs, used in apps. Do not change.
INFO_LOGGER = "info_logger"
ERROR_LOGGER = "error_logger"

# Separator used to join different logged features.
LOGGING_SEPARATOR = " - "

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": LOGGING_SEPARATOR.join(
                [
                    "%(levelname)s",
                    "%(module)s",
                    "function: %(funcName)s",
                    "line: %(lineno)s",
                    "%(name)s",
                    "PID: %(process)d",
                    "TID: %(thread)d",
                    "%(message)s",
                    "%(asctime)-15s",
                ]
            ),
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
        "detailed_error": {
            "format": "\n"
            + LOGGING_SEPARATOR.join(
                [
                    "%(levelname)s",
                    "%(module)s",
                    "%(name)s",
                    "PID: %(process)d",
                    "TID: %(thread)d",
                    "%(funcName)s",
                    "%(message)s",
                    "%(asctime)-15s",
                ]
            )
        },
    },
    "handlers": {
        "info_file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "formatter": "detailed",
            "filename": INFO_LOG_FILE_NAME,
            "encoding": "utf8",
            "mode": "a",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "formatter": "detailed_error",
            "filename": ERROR_LOG_FILE_NAME,
            "encoding": "utf8",
            "mode": "a",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "detailed",
        },
    },
    "loggers": {
        INFO_LOGGER: {
            "level": "INFO",
            "handlers": ["info_file"],
            "propagate": True,
        },
        ERROR_LOGGER: {
            "level": "ERROR",
            "handlers": ["console", "error_file"],
        },
        # Big parent of all the Django loggers, MOST (not all) of this will get overwritten.
        # https://docs.djangoproject.com/en/2.1/topics/logging/#topic-logging-parts-loggers
        "django": {"handlers": ["console", "error_file"], "level": "ERROR"},
        # Log messages related to the handling of requests.
        # 5XX responses are raised as ERROR messages; 4XX responses are raised as WARNING messages
        "django.request": {
            "handlers": ["error_file", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        # Log messages related to the handling of requests received by the server invoked by the runserver command.
        # HTTP 5XX responses are logged as ERROR messages, 4XX responses are logged as WARNING messages,
        # everything else is logged as INFO.
        "django.server": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
