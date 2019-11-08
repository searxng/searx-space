import argparse
import asyncio

from searxstats.instances import SEARX_INSTANCES_URL
from searxstats.searxstats import MODULE_DEFINITION, run_once, run_server, initialize


def run(server_mode, output_file, instance_urls=None, modules=None):
    if server_mode:
        print('🤖 Server mode')
        run_function = run_server
    else:
        print('⚡ Single run')
        run_function = run_once
    print('{0:15} : {1}'.format('Output file', output_file))
    for module in MODULE_DEFINITION:
        module_name = module['name']
        value = 'yes' if module_name in modules else 'no'
        print('{0:15} : {1}'.format(module_name, value))

    initialize()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_function(output_file,
                                         instance_urls=instance_urls,
                                         modules=modules))


def run_from_command_line():
    parser = argparse.ArgumentParser(description='Check searx instances.')
    parser.add_argument('--output', '-o',
                        type=str, nargs='?', dest='output',
                        help='JSON output file name',
                        default='html/data/instances.json')
    parser.add_argument('--server', '-s',
                        action='store_true', dest='server_mode',
                        help='Server mode, automatic check every day',
                        default=False)
    parser.add_argument('--all',
                        action='store_true', dest='all',
                        help='Activate all modules',
                        default=False)
    for module in MODULE_DEFINITION:
        parser.add_argument('--' + module['name'], dest=module['name'],
                            help=module['help'], action='store_true',
                            default=False)
    for module in MODULE_DEFINITION:
        parser.add_argument('--update-' + module['name'], dest='update-' + module['name'],
                            help='Same as --' + module['name']+ ' but ignore cache', action='store_true',
                            default=False)
    parser.add_argument('instance_urls', metavar='instance_url', type=str, nargs='*',
                        help='instance URLs, otherwise fetch URLs from {0}'
                        .format(SEARX_INSTANCES_URL))

    args = parser.parse_args()
    args_vars = vars(args)

    selected_modules = set()
    for module in MODULE_DEFINITION:
        module_name = module['name']
        if args_vars.get(module_name, False) or args.all:
            selected_modules.add(module_name)
        if args_vars.get('update-' + module_name, False) or args.all:
            selected_modules.add(module_name)

    run(args.server_mode,
        args.output,
        instance_urls=args.instance_urls,
        modules=list(selected_modules))


if __name__ == '__main__':
    run_from_command_line()
