import os
import json
import shutil
import hashlib
import base64

import jinja2
import brotli
from ..model import SearxStatisticsResult
from .context import get_context
from .filters import set_environment



def write_file(file_name, content):
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'w') as stream:
        stream.write(content)


def write_json(searx_stats_result: SearxStatisticsResult, output_file: str):
    searx_json = searx_stats_result.get_json()
    result = json.dumps(searx_json, indent=4, ensure_ascii=False)
    write_file(output_file, result)


def write_template(searx_stats_result: SearxStatisticsResult, output_file: str, template: jinja2.Template):
    context = get_context(searx_stats_result, template)
    result = template.render(context)
    write_file(output_file, result)


def write_templates(searx_stats_result: SearxStatisticsResult, static_urls: dict, output_directory: str):
    def _link(href: str, rel='stylesheet') -> str:
        url = static_urls[href]["url"]
        # not sure if it works if the file are served from a .onion, doesn't work on localhost
        # integrity = static_urls[href]["integrity"]
        # return f'<link rel="{rel}" integrity="{integrity}" crossorigin="same-origin" href="{url}"/>'
        return f'<link rel="{rel}" href="{url}"/>'

    def _script(href: str) -> str:
        url = static_urls[href]["url"]
        return f'<script src="{url}"></script>'

    output_directory = os.path.realpath(output_directory)
    current_directory = os.path.dirname(os.path.realpath(__file__))
    templates_directory = os.path.join(current_directory, 'templates')

    environment = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_directory))
    environment.globals['link'] = _link
    environment.globals['script'] = _script
    set_environment(environment)

    for template_name in environment.list_templates():
        if not template_name.startswith('macros'):
            template = environment.get_template(template_name)
            output_file = os.path.join(output_directory, template_name)
            write_template(searx_stats_result, output_file, template)


def get_sha256_file(file_name: str) -> str:
    with open(file_name, 'rb') as stream:
        content = stream.read()
        digest = hashlib.sha256(content).digest()
        return base64.b64encode(digest).decode('ascii')


def add_sha_to_name(file_name: str, sha: str) -> str:
    betweendots = file_name.split('.')
    if len(betweendots) < 2:
        return file_name
    if betweendots[-1] not in ('css', 'js'):
        return file_name
    if len(betweendots) > 2 and betweendots[-2] == 'min':
        index = -2
    else:
        index = -1
    minsha = sha[:16].replace('+', '-').replace('/', '_').replace('=', '')
    betweendots.insert(index, minsha)
    return '.'.join(betweendots)


def write_statics(output_directory: str):
    current_directory = os.path.dirname(os.path.realpath(__file__))
    static_directory = os.path.join(current_directory, 'static')
    static_urls = dict()
    for root, _, files in os.walk(static_directory, topdown=False, followlinks=True):
        for name in files:
            from_file_name = os.path.join(root, name)
            if from_file_name.startswith(static_directory):
                relative_file_name = from_file_name[len(static_directory)+1:]
                sha256 = get_sha256_file(from_file_name)
                relative_file_name_sha = add_sha_to_name(relative_file_name, sha256)
                static_urls[relative_file_name] = {'url': relative_file_name_sha, 'integrity': 'sha256-' + sha256}

                to_file_name = os.path.realpath(os.path.join(output_directory, relative_file_name_sha))
                os.makedirs(os.path.dirname(to_file_name), exist_ok=True)
                shutil.copy(from_file_name, to_file_name)
                shutil.copystat(from_file_name, to_file_name)
            else:
                print('Internal Error', static_directory, from_file_name)
    return static_urls


def write_compressed_files(output_directory: str):
    for root, _, files in os.walk(output_directory, topdown=False, followlinks=True):
        for name in files:
            file_name = os.path.join(root, name)
            with open(file_name, 'rb') as stream:
                content = stream.read()
            brotli_content = brotli.compress(content)
            brotli_file_name = file_name + '.br'
            with open(brotli_file_name, 'wb') as stream:
                stream.write(brotli_content)
            shutil.copystat(file_name, brotli_file_name)


def write(searx_stats_result: SearxStatisticsResult, output_directory: str):
    static_urls = write_statics(output_directory)
    write_templates(searx_stats_result, static_urls, output_directory)
    write_json(searx_stats_result, os.path.join(output_directory, 'data/instances.json'))
    write_compressed_files(output_directory)
