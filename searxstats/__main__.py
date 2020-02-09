import argparse
import asyncio

from .common.memoize import bind_to_file_name
from .config import CACHE_DIRECTORY, SEARXINSTANCES_GIT_REPOSITORY, set_cache_directory, get_cache_file_name
from .fetcher import FETCHERS
from . import initialize, run_once, run_server, erase_memoize, finalize


# pylint: disable=too-many-arguments
def run(server_mode: bool, output_file_name: str, user_cache_directory: str,
        instance_urls: list, selected_fetcher_names: list, update_fetcher_memoize_list: list):
    if server_mode:
        print('🤖 Server mode')
        run_function = run_server
    else:
        print('⚡ Single run')
        run_function = run_once
    print('{0:15} : {1}'.format('Output file', output_file_name))
    print('{0:15} : {1}'.format('Cache directory', user_cache_directory))
    for fetcher in FETCHERS:
        fetcher_name = fetcher.name
        value = 'yes' if fetcher_name in selected_fetcher_names else 'no'
        if fetcher_name in update_fetcher_memoize_list:
            value = value + ' (force update)'
        print('{0:15} : {1}'.format(fetcher_name, value))

    loop = asyncio.get_event_loop()

    # initialize
    loop.run_until_complete(initialize())

    try:
        # set cache directory
        set_cache_directory(user_cache_directory)

        # load cache
        bind_to_file_name(get_cache_file_name())

        # erase cache entries to update
        erase_memoize(update_fetcher_memoize_list)

        # run
        loop.run_until_complete(run_function(output_file_name, instance_urls, selected_fetcher_names))
    finally:
        # finalize
        loop.run_until_complete(finalize())


def main():
    parser = argparse.ArgumentParser(description='Check searx instances.')
    parser.add_argument('--output', '-o',
                        type=str, nargs='?', dest='output_file_name',
                        help='JSON output file name',
                        default='html/data/instances.json')
    parser.add_argument('--cache',
                        type=str, nargs='?', dest='user_cache_directory',
                        help='Cache directory',
                        default=CACHE_DIRECTORY)
    parser.add_argument('--server', '-s',
                        action='store_true', dest='server_mode',
                        help='Server mode, automatic check every day',
                        default=False)
    parser.add_argument('--all',
                        action='store_true', dest='all',
                        help='Activate all fetchers',
                        default=False)
    for fetcher in FETCHERS:
        if not fetcher.mandatory:
            parser.add_argument('--' + fetcher.name, dest=fetcher.name,
                                help=fetcher.help_message, action='store_true',
                                default=False)
    parser.add_argument('--update-all',
                        action='store_true', dest='update_all',
                        help='Update all fetchers',
                        default=False)
    for fetcher in FETCHERS:
        parser.add_argument('--update-' + fetcher.name, dest='update_' + fetcher.name,
                            help='Same as --' + fetcher.name + ' but ignore the cached values', action='store_true',
                            default=False)
    parser.add_argument('instance_urls', metavar='instance_url', type=str, nargs='*',
                        help='instance URLs, otherwise use {0}'.format(SEARXINSTANCES_GIT_REPOSITORY))

    args = parser.parse_args()
    args_vars = vars(args)

    selected_fetcher_names = set()
    update_fetcher_memoize_list = set()
    for fetcher in FETCHERS:
        fetcher_name = fetcher.name
        if args_vars.get(fetcher_name, False) or args.all:
            selected_fetcher_names.add(fetcher_name)
        if args_vars.get('update_' + fetcher_name, False) or args.update_all:
            selected_fetcher_names.add(fetcher_name)
            update_fetcher_memoize_list.add(fetcher_name)

    run(args.server_mode,
        args.output_file_name,
        args.user_cache_directory,
        args.instance_urls,
        list(selected_fetcher_names),
        list(update_fetcher_memoize_list))


if __name__ == '__main__':
    main()
