import argparse
import asyncio

from searxstats.memoize import bind_to_file_name
from searxstats.config import DEFAULT_CACHE_FILE_NAME
from searxstats.instances import SEARX_INSTANCES_URL
from searxstats.fetcher import FETCHERS
from searxstats import initialize, run_once, run_server, erase_memoize


# pylint: disable=too-many-arguments
def run(server_mode: bool, output_file_name: str, cache_file_name: str,
        instance_urls: list, selected_fetcher_names: list, update_fetcher_memoize_list: list):
    if server_mode:
        print('🤖 Server mode')
        run_function = run_server
    else:
        print('⚡ Single run')
        run_function = run_once
    print('{0:15} : {1}'.format('Output file', output_file_name))
    print('{0:15} : {1}'.format('Cache file', cache_file_name))
    for fetcher in FETCHERS:
        fetcher_name = fetcher.name
        value = 'yes' if fetcher_name in selected_fetcher_names else 'no'
        if fetcher_name in update_fetcher_memoize_list:
            value = value + ' (force update)'
        print('{0:15} : {1}'.format(fetcher_name, value))

    # initialize
    initialize()

    # load cache
    bind_to_file_name(cache_file_name)

    # erase cache entries to update
    erase_memoize(update_fetcher_memoize_list)

    # run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_function(output_file_name, instance_urls, selected_fetcher_names))


def main():
    parser = argparse.ArgumentParser(description='Check searx instances.')
    parser.add_argument('--output', '-o',
                        type=str, nargs='?', dest='output_file_name',
                        help='JSON output file name',
                        default='html/data/instances.json')
    parser.add_argument('--cache',
                        type=str, nargs='?', dest='cache_file_name',
                        help='Cache file',
                        default=DEFAULT_CACHE_FILE_NAME)
    parser.add_argument('--server', '-s',
                        action='store_true', dest='server_mode',
                        help='Server mode, automatic check every day',
                        default=False)
    parser.add_argument('--all',
                        action='store_true', dest='all',
                        help='Activate all fetchers',
                        default=False)
    for fetcher in FETCHERS:
        parser.add_argument('--' + fetcher.name, dest=fetcher.name,
                            help=fetcher.help_message, action='store_true',
                            default=False)
    parser.add_argument('--update-all',
                        action='store_true', dest='update_all',
                        help='Update all fetchers',
                        default=False)
    for fetcher in FETCHERS:
        parser.add_argument('--update-' + fetcher.name, dest='update_' + fetcher.name,
                            help='Same as --' + fetcher.name+ ' but ignore the cached values', action='store_true',
                            default=False)
    parser.add_argument('instance_urls', metavar='instance_url', type=str, nargs='*',
                        help='instance URLs, otherwise fetch URLs from {0}'
                        .format(SEARX_INSTANCES_URL))

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
        args.cache_file_name,
        args.instance_urls,
        list(selected_fetcher_names),
        list(update_fetcher_memoize_list))


if __name__ == '__main__':
    main()
