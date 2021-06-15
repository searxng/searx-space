import typing

from sqlalchemy import select
from sqlalchemy.orm import lazyload

from searxstats.database import get_engine, new_session, Commit, Content, Fork
from searxstats.data.dynamic_hashes import DYNAMIC_HASHES
from searxstats.data.inline_hashes import INLINE_HASHES


def get_fork_list():
    fork_list = [
        'https://github.com/searx/searx'
    ]
    with get_engine().connect() as connection:
        with new_session(bind=connection) as session:
            for fork in session.query(Fork).options(lazyload(Fork.commits)):
                git_url = fork.git_url
                if git_url not in fork_list:
                    fork_list.append(git_url)
    return fork_list


def get_repositories_for_content_sha(content_sha):
    result: typing.List[str] = []
    with get_engine().connect() as connection:
        with new_session(bind=connection) as session:
            s = select(Fork.git_url) \
                .join(Fork.commits) \
                .join(Commit.contents) \
                .filter(Content.sha == content_sha) \
                .group_by(Fork.git_url)
            for row in session.execute(s):
                result.append(row[0])
    return result


def is_wellknown_content_sha(content_sha):
    return content_sha in INLINE_HASHES or content_sha in DYNAMIC_HASHES


def is_commit_exists(session, commit_sha):
    commit_obj = session.query(Commit)\
                        .options(lazyload(Commit.contents))\
                        .where(Commit.sha == commit_sha)\
                        .scalar()
    return commit_obj is not None


def get_all_commit_list(repo):
    commit_list = list(repo.iter_commits())
    commit_list.reverse()
    return commit_list
