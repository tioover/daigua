import os
import support
import mistune
import shutil
import urllib.parse
import re

default_config = {
    'templates_path': 'templates',
    'target_path': 'target',
    'document_path': 'document',
}

config = support.load_config(default_config)
templates_path = config['templates_path']
target_path = config['target_path']
document_path = config['document_path']
env = support.build_template_environment(templates_path)
logger = support.build_logger()

HTML_EXT = ('.html', '.htm')
MARKDOWN_EXT = ('.markdown', '.md')


class DaiGuaRenderer(mistune.Renderer):
    info = dict()

    def paragraph(self, text):
        text = text.strip(' ')
        if 'excerpt' not in self.info:
            self.info['excerpt'] = text
        return '<p>%s</p>\n' % text

    def header(self, text, level, raw=None):
        if level == 1:
            self.info['title'] = text
        return '<h{0} id="{2}">{1}</h{0}><a href="#{2}" class="header-link">¶</a>\n'.format(level, text, urllib.parse.quote(text))


markdown = mistune.Markdown(renderer=DaiGuaRenderer())


def markdown_render(text):
    markdown.renderer.info = dict()
    result = markdown.render(text)
    info = markdown.renderer.info.copy()
    markdown.renderer.info.clear()
    return result, info


class Site:
    def __init__(self):
        self.title = config['title']
        self.posts = []
        self.pages = []
        self.statics = []
        self.categories = dict()

        for (path, files) in support.walk(templates_path, Site.is_ignore):
            relative = os.path.relpath(path, start=templates_path)
            for file in files:
                name, ext = os.path.splitext(file)
                if ext in HTML_EXT or ext in MARKDOWN_EXT:
                    self.pages.append(Page(file, relative, path))
                else:
                    self.statics.append(Static(file, relative, path))

        for (path, files) in support.walk(document_path, Site.is_ignore):
            relative = os.path.relpath(path, start=document_path)
            for file in files:
                name, ext = os.path.splitext(file)
                if ext in HTML_EXT or ext in MARKDOWN_EXT:
                    self.posts.append(Post(file, relative, path, self.categories))
                else:
                    self.statics.append(Static(file, relative, path))

    def build(self):
        for post in self.posts:
            post.build(self)
        for page in self.pages:
            page.build(self)
        for static in self.statics:
            static.build()

    @staticmethod
    def is_ignore(name: str):
        return name.startswith('_')


class Resource:
    def __init__(self, filename, relative, location, output_name=None):
        self.filename = filename
        self.output_name = output_name or filename
        self.relative = relative
        self.location = location

        base = config['base_url'] if 'base_url' in config else '/'
        self.url = urllib.parse.urljoin(base, os.path.join(relative, output_name))

        self.output_location = os.path.join(target_path, relative)
        self.source_path = os.path.join(location, filename)
        self.output_path = os.path.join(self.output_location, output_name)

    def read(self):
        with open(self.source_path, encoding='utf-8') as file:
            return file.read()

    def write(self, data):
        if not os.path.exists(self.output_location):
            os.makedirs(self.output_location)
        with open(self.output_path, mode='w', encoding='utf-8') as file:
            file.write(data)


class Page(Resource):

    def __init__(self, filename, relative, location):
        name, ext = os.path.splitext(filename)
        super().__init__(filename, relative, location, '{}.html'.format(name))

        self.markdown = ext in MARKDOWN_EXT
        self.layout = None
        if self.markdown:
            self.layout = 'default'
        self.display = True
        self.context = dict()
        self.excerpt = ''

    def build(self, site):
        if not self.display:
            return
        source = self.read()
        if self.markdown:
            source, context = markdown_render(source)
            self.context.update(context)
        if 'excerpt' in self.context:
            self.excerpt = self.context['excerpt']

        if self.layout:
            source = """{{% extends "_layout/{layout}.html" %}}
            {{% block content %}}{content}{{% endblock %}}""".format(
                layout=self.layout, content=source)
        template = env.from_string(source)
        self.write(template.render(self.context, page=self, site=site))


# FILENAME_DATE = re.compile(r'^(\d+-\d+-\d+)')

class Post(Page):
    def __init__(self, filename, relative, location, categories: dict):
        super().__init__(filename, relative, location)
        _, category = os.path.split(relative)

        self.date = support.creation_time(self.source_path)
        if not category or category == '.':
            self.category = None
        else:
            self.layout = 'post'
            self.category = category
            if category in categories:
                categories[category].append(self)
            else:
                categories[category] = [self, ]


class Static(Resource):
    def __init__(self, filename, relative, location):
        super().__init__(filename, relative, location)

    def build(self):
        src = os.path.join(self.location, self.filename)
        dst = os.path.join(target_path, self.relative, self.filename)
        shutil.copy(src, dst)


def generate():
    site = Site()
    site.build()


if __name__ == '__main__':
    generate()

