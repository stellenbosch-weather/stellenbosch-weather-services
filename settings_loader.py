from __future__ import absolute_import

import os

try:
    import configparser
except ImportError:  # Python 2
    import ConfigParser as configparser


SERVICE_ROOT = os.path.dirname(os.path.abspath(__file__))


def settings_candidates():
    candidates = [
        os.path.abspath("settings.conf"),
        os.path.join(SERVICE_ROOT, "settings.conf"),
        os.path.join(os.path.dirname(SERVICE_ROOT), "settings.conf"),
        os.path.expanduser("~/settings.conf"),
    ]

    unique_candidates = []
    for path in candidates:
        path = os.path.abspath(path)
        if path not in unique_candidates:
            unique_candidates.append(path)
    return unique_candidates


def find_settings_file():
    for path in settings_candidates():
        if os.path.isfile(path):
            return path

    raise IOError(
        "No settings.conf found. Checked: {0}".format(
            ", ".join(settings_candidates())
        )
    )


def load_settings():
    settings_file = find_settings_file()
    config = configparser.ConfigParser()
    with open(settings_file) as handle:
        if hasattr(config, "read_file"):
            config.read_file(handle)
        else:  # Python 2
            config.readfp(handle)
    return config


def load_database_settings():
    config = load_settings()
    return {
        "host": config.get("database", "host"),
        "user": config.get("database", "username"),
        "password": config.get("database", "password"),
        "database": config.get("database", "database"),
    }
