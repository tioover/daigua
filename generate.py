import datetime
import os
import re
import shutil
from pathlib import Path

import mistune
from typing import Tuple

import support

default_config = {
    'site_path': 'site',
    'target_path': 'target',
    'document_path': 'document',
}

config = support.load_config(default_config)
site_path = Path(config['site_path'])
target_path = Path(config['target_path'])
env = support.build_template_environment(site_path)
logger = support.build_logger()

TEMPLATE_EXT = ('.html', '.htm')
MARKDOWN_EXT = ('.markdown', '.md')


class Markdown:
    META_SEPARATOR = re.compile(r"^---\n(.*)---\n", re.DOTALL)

    class Renderer(mistune.Renderer):
        info = dict()

        def paragraph(self, text):
            text = text.strip(' ')
            if 'excerpt' not in self.info:
                self.info['excerpt'] = text
            return '<p>%s</p>\n' % text

        def header(self, text, level, raw=None):
            if level == 1:
                self.info['title'] = text
            escape = support.url_escape(text)
            return '<h{0} id="{2}">{1}</h{0}>\n'.format(level, text, escape)

    def __init__(self):
        self.renderer = Markdown.Renderer()
        self.markdown = mistune.Markdown(renderer=self.renderer)

    def render(self, text):
        searched = self.META_SEPARATOR.search(text)
        meta = dict()
        if searched:
            text = text[searched.end():]
            meta = support.yaml_load(searched.group(1))
            if 'excerpt' in meta:
                meta['excerpt'] = self.markdown.render(meta['excerpt'])
        self.renderer.info.clear()
        result = self.markdown.render(text)
        info = self.renderer.info.copy()
        self.renderer.info.clear()
        info.update(meta)
        return result, info


markdown = Markdown()


class Site:
    def __init__(self):
        self.config = config
        self.title = config['title']
        self.pages = []
        self.statics = []
        self.categories = dict()

        for (path, files) in support.walk(site_path, Site.is_ignore):
            assert isinstance(path, Path)
            for file in files:
                assert isinstance(file, Path)
                if file.suffix in TEMPLATE_EXT or file.suffix in MARKDOWN_EXT:
                    self.pages.append(Page(file, path))
                else:
                    self.statics.append(Static(file, path))

    def build(self):
        for page in self.pages:
            page.build(self)
        for static in self.statics:
            static.build()

    @staticmethod
    def is_ignore(name: str):
        return name.startswith('_')

    def __getattr__(self, item):
        if item not in config:
            raise AttributeError
        else:
            return config[item]


class Resource:
    def __init__(self, filename: Path, relative: Path, output_name=None):
        self.filename = filename
        self.output_name = output_name or filename
        self.location = site_path / relative

        base = config['base_url'] if 'base_url' in config else '/'
        self.url = base / relative / output_name

        self.source_path = self.location / filename
        self.output_path = target_path / relative / self.output_name

    def read(self):
        with open(self.source_path, encoding='utf-8') as file:
            return file.read()

    def write(self, data):
        if not self.output_path.parent.exists():
            os.makedirs(self.output_path.parent)
        with open(self.output_path, mode='w', encoding='utf-8') as file:
            file.write(data)


class Page(Resource):
    POST_PATTERN = re.compile(r'^(\d+)-(\d+)-(\d+)-.+')

    def __init__(self, filename: Path, relative: Path):
        super().__init__(filename, relative, '{}.html'.format(filename.stem))

        self.post, self.date = self.page_type_and_creation(filename)
        self.markdown = filename.suffix in MARKDOWN_EXT
        self.meta = {
            'layout': '',
            'category': '',
            'published': True,
            'excerpt': '',
        }
        if self.markdown:
            self.meta['layout'] = 'default'
            self.meta['category'] = relative.name
        if self.post:
            self.meta['layout'] = 'post'
        self.source = self.render()
        if 'title' in self.meta:
            self.title = self.meta['title']
        else:
            self.title = str(filename.stem)

    def __getattr__(self, item):
        if item not in self.meta:
            raise AttributeError
        else:
            return self.meta[item]

    def page_type_and_creation(self, filename) -> Tuple[bool, datetime.datetime]:
        filename = str(filename)
        match = self.POST_PATTERN.match(filename)
        if match:
            year = match.group(1)
            if len(year) == 2:
                year = int('20' + year)
            month = int(match.group(2))
            day = int(match.group(3))
            return True, datetime.datetime(year, month, day)
        else:
            return False, support.creation_time(self.source_path)

    def render(self):
        source = self.read()
        if self.markdown:
            source, context = markdown.render(source)
            self.meta.update(context)
        if self.meta['layout']:
            source = """{{% extends "_layout/{layout}.html" %}}
            {{% block content %}}{content}{{% endblock %}}""".format(
                layout=self.meta['layout'], content=source)
        return source

    def build(self, site):
        if not self.meta['published']:
            return
        template = env.from_string(self.source)
        self.write(template.render(self.meta, page=self, site=site))


class Static(Resource):
    def __init__(self, filename, relative):
        super().__init__(filename, relative)

    def build(self):
        shutil.copy(str(self.source_path), str(self.output_path))


def generate():
    site = Site()
    site.build()


if __name__ == '__main__':
    generate()
