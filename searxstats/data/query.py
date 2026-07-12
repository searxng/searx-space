import typing

from sqlalchemy import select, func

from searxstats.database import get_engine, new_session, Commit, Content, Fork
from searxstats.data.dynamic_hashes import DYNAMIC_HASHES
from searxstats.data.inline_hashes import INLINE_HASHES


def get_repositories_for_content_sha(content_sha):
    result: typing.List[str] = []
    with get_engine().connect() as connection:
        with new_session(bind=connection) as session:
            # order_by: to get the oldest commits first
            s = select(Fork.git_url, func.min(Commit.date)) \
                .join(Fork.commits) \
                .join(Commit.contents) \
                .filter(Content.sha == content_sha) \
                .group_by(Fork.git_url) \
                .order_by(func.min(Commit.date))
            for row in session.execute(s):
                result.append(row[0])
    return result


def is_wellknown_content_sha(content_sha):
    return content_sha in INLINE_HASHES or content_sha in DYNAMIC_HASHES


def get_all_commit_list(repo):
    commit_list = list(repo.iter_commits())
    commit_list.reverse()
    return commit_list
