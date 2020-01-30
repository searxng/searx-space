# pylint: skip-file
import searxstats.common.git_tool
import searxstats.config

SEARX_INSTANCES_URL = None


async def get_instance_urls():
    # TEMPORARY
    global SEARX_INSTANCES_URL  # pylint: disable=global-statement
    repo_directory = searxstats.config.get_searxinstances_repository_directory()
    searxstats.common.git_tool.get_repository(repo_directory, searxstats.config.SEARXINSTANCES_GIT_REPOSITORY)

    import sys  # pylint: disable=import-outside-toplevel
    sys.path.append(repo_directory)

    import searxinstances.model  # pylint: disable=import-outside-toplevel

    SEARX_INSTANCES_URL = searxinstances.model.FILENAME

    instance_list = searxinstances.model.load()

    result = list(instance_list.urls)
    result.sort()
    return result
