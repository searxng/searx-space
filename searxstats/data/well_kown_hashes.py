import typing
import os
import hashlib

from sqlalchemy.orm import lazyload
from sqlalchemy import select

import searxstats.common.git_tool as git_tool
from searxstats.database import get_engine, new_session, Commit, Content, Fork, commit_content_table
from searxstats.config import get_git_repository_path


__all__ = ['fetch_file_content_hashes', 'get_repositories_for_content_sha']


def get_filename_list(repo_directory):
    static_directory = os.path.join(repo_directory, 'searx', 'static')
    # create a list of file and sub directories
    # names in the given directory
    all_files = list()
    # Iterate over all the entries
    for root, _, files in os.walk(static_directory, topdown=False, followlinks=True):
        for name in files:
            filename = os.path.join(root, name)
            if not filename.endswith('.less'):
                all_files.append(filename)
    return all_files


def get_file_content_hash(filename):
    with open(filename, 'rb') as reader:
        buffer = reader.read()
        return hashlib.sha256(buffer).hexdigest()


def get_content_list_per_commit_iterator(repo_directory, repo, commit_list):
    seen_content_hashes = set()
    commit_count = len(commit_list)
    count = 1
    for commit in commit_list:
        repo.git.checkout(commit)
        # get hashes
        content_for_commit = set()
        for filename in get_filename_list(repo_directory):
            content_hash = get_file_content_hash(filename)
            content_for_commit.add(content_hash)
            seen_content_hashes.add(content_hash)
        # yield
        yield str(commit.hexsha), content_for_commit
        # output
        if count % 50 == 0 or (commit_count - count) < 5 or count == 1:
            print('commit {:4} of {:4}: {:4} different hashes'.format(
                count, commit_count, len(seen_content_hashes)))
        count = count + 1


def get_all_commit_list(repo):
    commit_list = list(repo.iter_commits())
    commit_list.reverse()
    return commit_list


def fetch_file_content_hashes(repo_url=None):
    # get repo_directory from the repo_url
    repo_directory = get_git_repository_path(repo_url)
    # get (or initialize) the git repository
    repo = git_tool.get_repository(repo_directory, repo_url)
    # get commit list
    all_commit_list = get_all_commit_list(repo)
    # forks
    with get_engine().connect() as connection:
        with new_session(bind=connection) as session:
            # get fork_obj
            fork_obj = session.execute(
                                    select(Fork)
                                    .where(Fork.git_url == repo_url)
                               ).scalar()
            if fork_obj is None:
                fork_obj = Fork(git_url=repo_url)
                session.add(fork_obj)

            # get the existing commits
            existing_commit_obj = session.execute(
                                    select(Commit)
                                    .where(Commit.sha.in_([commit.hexsha for commit in all_commit_list]))
                                  ).all()
            existing_commit_sha_tuple = tuple(commit_obj[0].sha for commit_obj in existing_commit_obj)
            new_commit_list = [commit for commit in all_commit_list if commit.hexsha not in existing_commit_sha_tuple]

            print('  {:5} existing commit(s)'.format(len(existing_commit_sha_tuple)))
            for row in existing_commit_obj:
                commit_obj = row[0]
                if fork_obj not in commit_obj.forks:
                    commit_obj.forks.append(fork_obj)
                    session.add(commit_obj)
            session.commit()

            del fork_obj
            del existing_commit_obj
            del existing_commit_sha_tuple

        print('  {:5} new commit(s)'.format(len(new_commit_list)))

        commit_iterator = get_content_list_per_commit_iterator(repo_directory, repo, new_commit_list)
        for commit_sha, content_hash_list in commit_iterator:
            # one SQL transaction per commit
            with new_session(bind=connection) as session:
                # get fork_obj
                fork_obj = session.query(Fork)\
                                  .where(Fork.git_url == repo_url)\
                                  .scalar()

                # add / update commit_obj
                # don't load commit_obj.contents
                commit_obj = session.query(Commit)\
                                    .options(lazyload(Commit.contents))\
                                    .where(Commit.sha == commit_sha)\
                                    .scalar()
                if not commit_obj:
                    commit_obj = Commit(sha=commit_sha, forks=[fork_obj])
                    session.add(commit_obj)
                elif fork_obj not in commit_obj.forks:
                    commit_obj.forks.append(fork_obj)
                    session.add(commit_obj)

                # add new content_obj
                result_dict = {}
                for content_obj in session.query(Content).options(lazyload(Content.commits)):
                    result_dict[content_obj.sha] = content_obj.id
                new_content_list = [content_hash
                                    for content_hash in content_hash_list
                                    if content_hash not in result_dict]
                if new_content_list:
                    session.execute(Content.__table__.insert(), [{"sha": sha} for sha in new_content_list])

                # add links between commit_obj and the content_obj list
                content_id_list = session.query(Content.id)\
                                         .where(Content.sha.in_(content_hash_list))\
                                         .all()
                session.execute(commit_content_table.insert(),
                                [{"commit_id": commit_obj.id, "content_id": content_id[0]}
                                 for content_id in content_id_list])
                session.commit()


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
