import os

from sqlalchemy import select

import searxstats.common.git_tool as git_tool
from searxstats.common.utils import get_file_content_hash
from searxstats.database import get_engine, new_session, Commit, Fork
from searxstats.config import get_git_repository_path
from searxstats.data.update import insert_commit
from searxstats.data.query import get_all_commit_list


__all__ = ['fetch_hashes_from_git_url']


def get_filename_list(repo_directory):
    static_directory = os.path.join(repo_directory, 'searx', 'static')
    if not os.path.isdir(static_directory):
        # if searx/static is not found,
        # fallback to the whole git repository to deal with some forks
        static_directory = repo_directory
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
        yield str(commit.hexsha), commit.authored_date, content_for_commit
        # output
        if count % 50 == 0 or (commit_count - count) < 5 or count == 1:
            print('commit {:4} of {:4}: {:4} different hashes'.format(
                count, commit_count, len(seen_content_hashes)))
        count = count + 1


def fetch_hashes_from_git_url(git_url=None):
    # get repo_directory from the repo_url
    repo_directory = get_git_repository_path(git_url)
    # get (or initialize) the git repository
    repo = git_tool.get_repository(repo_directory, git_url)
    # get commit list
    all_commit_list = get_all_commit_list(repo)
    # forks
    with get_engine().connect() as connection:
        with new_session(bind=connection) as session:
            # get fork_obj
            fork_obj = session.execute(
                                    select(Fork)
                                    .where(Fork.git_url == git_url)
                               ).scalar()
            if fork_obj is None:
                fork_obj = Fork(git_url=git_url)
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
        for commit_sha, commit_date, content_hash_list in commit_iterator:
            # one SQL transaction per commit
            with new_session(bind=connection) as session:
                insert_commit(session, git_url, commit_sha, commit_date, content_hash_list)
                session.commit()
