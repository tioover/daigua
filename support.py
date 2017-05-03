import datetime
import logging
import os
import time
import urllib.parse
from pathlib import Path

import jinja2
import yaml
from typing import Callable, Tuple, List, Iterable

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def yaml_load(stream) -> dict:
    return yaml.load(stream, Loader=Loader)


def yaml_dump(obj: dict) -> str:
    return yaml.dump(obj, Dumper=Dumper)


def build_template_environment(templates_path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_path)),
        lstrip_blocks=True,
    )


def load_config(default: dict) -> dict:
    config_file_name = 'config.yaml'
    with open(config_file_name) as config_file:
        config = yaml_load(config_file)
    default.update(config)
    return default


def build_logger() -> logging.Logger:
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    return logger


def walk(path, is_ignore: Callable[[str], bool]) -> Iterable[Tuple[Path, List[Path]]]:
    for (root, dirs, files) in os.walk(path):
        dirs[:] = [dir_name for dir_name in dirs if not is_ignore(dir_name)]
        files = [Path(file) for file in files if not is_ignore(file)]
        yield (Path(root).relative_to(path), files)


def creation_time(path) -> datetime.datetime:
    ctime = time.ctime(os.path.getctime(str(path)))
    return datetime.datetime.strptime(ctime, "%a %b %d %H:%M:%S %Y")


def url_escape(s: str) -> str:
    s = s.replace(' ', '_').lower()
    return urllib.parse.quote(s)
