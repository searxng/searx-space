import argparse
import asyncio

from .common.memoize import bind_to_file_name
from .config import (
    CACHE_DIRECTORY, DATABASE_URL, SEARXINSTANCES_GIT_REPOSITORY, IP2LOCATION_FILENAME,
    set_cache_directory, set_database_url, get_cache_file_name)
from .fetcher import FETCHERS
from . import initialize, run_once, run_server, erase_memoize, finalize


# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals
def run(server_mode: bool, output_file_name: str, user_cache_directory: str, database_url: str,
        instance_urls: list, private: bool, selected_fetcher_names: list, update_fetcher_memoize_list: list):
    private_str = 'Private' if private else 'Public'
    server_mode_str = 'server mode' if server_mode else 'single run'
    server_emoji_str = '🤖' if server_mode else '⚡'
    print('{0} {1} {2}'.format(server_emoji_str, private_str, server_mode_str))
    print('{0:15} : {1}'.format('Output file', output_file_name))
    print('{0:15} : {1}'.format('Cache directory', user_cache_directory))
    print('{0:15} : {1}'.format('Database URL', database_url))
    print('{0:15} : {1}'.format('IP2Location', IP2LOCATION_FILENAME or ''))
    if server_mode:
        run_function = run_server
    else:
        run_function = run_once
    for fetcher in FETCHERS:
        fetcher_name = fetcher.name
        value = 'yes' if fetcher_name in selected_fetcher_names else 'no'
        if fetcher_name in update_fetcher_memoize_list:
            value = value + ' (force update)'
        print('{0:15} : {1}'.format(fetcher_name, value))

    loop = asyncio.get_event_loop()

    # set database URL
    set_database_url(database_url)

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
        loop.run_until_complete(run_function(output_file_name, private, instance_urls, selected_fetcher_names))
    finally:
        # finalize
        loop.run_until_complete(finalize())


def main():
    parser = argparse.ArgumentParser(description='Check searx instances.')
    parser.add_argument('--output', '-o',
                        type=str, nargs='?', dest='output_file_name',
                        help='JSON output file name',
                        default='html/data/instances.json')
    parser.add_argument('--private',
                        action='store_true', dest='private',
                        help='In private execution mode, fetch data even if the website is not a searx instance',
                        default=False)
    parser.add_argument('--cache',
                        type=str, nargs='?', dest='user_cache_directory',
                        help='Cache directory',
                        default=CACHE_DIRECTORY)
    parser.add_argument('--database',
                        type=str, nargs='?', dest='database_url',
                        help='Database URL',
                        default=DATABASE_URL)
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
        if args_vars.get(fetcher_name, False) or args.all or fetcher.mandatory:
            selected_fetcher_names.add(fetcher_name)
        if args_vars.get('update_' + fetcher_name, False) or args.update_all:
            selected_fetcher_names.add(fetcher_name)
            update_fetcher_memoize_list.add(fetcher_name)

    if len(args.instance_urls) == 0 and args.private:
        print('Missing URLs')
    else:
        run(args.server_mode,
            args.output_file_name,
            args.user_cache_directory,
            args.database_url,
            args.instance_urls,
            args.private,
            list(selected_fetcher_names),
            list(update_fetcher_memoize_list))


if __name__ == '__main__':
    main()
