# Separator used to join different logged features.
import logging


LOGGING_SEPARATOR = " - "


def setup_logging(info_log_file_name, error_log_file_name, info_logger, error_logger):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "\n"
                          + LOGGING_SEPARATOR.join(
                    [
                        "%(levelname)s",
                        "%(module)s",
                        "%(name)s",
                        "%(funcName)s",
                        "%(message)s",
                        "%(asctime)-15s",
                    ]
                )
            },
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
                "filename": info_log_file_name,
                "encoding": "utf8",
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.FileHandler",
                "formatter": "detailed_error",
                "filename": error_log_file_name,
                "encoding": "utf8",
            },
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
        },
        "loggers": {
            info_logger: {
                "level": "INFO",
                "handlers": ["info_file"],
                "propagate": True,
            },
            error_logger: {
                "level": "ERROR",
                "handlers": ["console", "error_file"],
            },
            "elasticsearch": {
                "level": logging.WARN,
                "handles": ["console"]
            },
            # Big parent of all the Django loggers, MOST (not all) of this will get overwritten.
            # https://docs.djangoproject.com/en/2.1/topics/logging/#topic-logging-parts-loggers
            "django": {"handlers": ["console", "error_file"], "level": "ERROR"},
            # Log messages related to the handling of requests.
            # 5XX responses are raised as ERROR messages; 4XX responses are raised as WARNING messages
            "django.request": {
                "handlers": ["console", "error_file"],
                "level": "ERROR",
                "propagate": False,
            },
            # Log messages related to the handling of requests received by the server invoked by the runserver command.
            # HTTP 5XX responses are logged as ERROR messages, 4XX responses are logged as WARNING messages,
            # everything else is logged as INFO.
            "django.server": {
                "handlers": ["console", "error_file"],
                "level": "ERROR",
                "propagate": False,
            },
        },
    }
