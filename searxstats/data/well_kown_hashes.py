import os
import hashlib
import yaml

import searxstats.common.git_tool as git_tool
from searxstats.config import get_hashes_file_name, get_git_repository_path, SEARX_GIT_REPOSITORY


__all__ = ['fetch_file_content_hashes']


def get_filename_list(directory):
    # create a list of file and sub directories
    # names in the given directory
    all_files = list()
    # Iterate over all the entries
    for root, _, files in os.walk(directory, topdown=False, followlinks=True):
        for name in files:
            all_files.append(os.path.join(root, name))
    return all_files


def get_all_commit_list(repo):
    commit_list = list(repo.iter_commits())
    commit_list.reverse()
    return commit_list


def get_file_content_hash(filename):
    with open(filename, 'rb') as reader:
        buffer = reader.read()
        return hashlib.sha256(buffer).hexdigest()


def is_static_file(filename):
    if filename.endswith('.less'):
        return False
    return True


def get_content_hash_list(repo_directory, repo, all_commits):
    content_hash_list = set()
    commit_count = len(all_commits)
    count = 1
    for commit in all_commits:
        # get hashes
        repo.git.checkout(commit)
        filename_list = get_filename_list(os.path.join(repo_directory, 'searx', 'static'))
        for filename in filename_list:
            if is_static_file(filename):
                content_hash_list.add(get_file_content_hash(filename))
        # output
        if count % 50 == 0 or (commit_count - count) < 5 or count == 1:
            print('commit {:4} of {:4}: {:4} different hashes'.format(
                count, commit_count, len(content_hash_list)))
        count = count + 1

    return list(content_hash_list)


def load(cache_file):
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as input_file:
                return yaml.safe_load(input_file)
        except Exception as ex:
            print(ex)
    return {
        'hashes': [],
        'commits': []
    }


def save(cache_file, result):
    content = yaml.safe_dump(result)
    with open(cache_file, 'w') as output_file:
        output_file.write(content)


def commit_list_to_hexsha_list(commit_list):
    return list(map(lambda commit: str(commit.hexsha), commit_list))


def commit_list_to_hexsha_dict(commit_list):
    return dict(map(lambda commit: (str(commit.hexsha), commit), commit_list))


def get_new_commit_list(all_commits, existing_hexsha_list):
    new_commits = list()
    for hexsha, commit in commit_list_to_hexsha_dict(all_commits).items():
        if hexsha not in existing_hexsha_list:
            new_commits.append(commit)
    return new_commits


def _fetch_file_content_hashes(cache_file, repo_directory, repo_url):
    # get (or initialize) the git repository
    repo = git_tool.get_repository(repo_directory, repo_url)

    # load existing hashes / commits
    result = load(cache_file)
    existing_commit_hexsha_list = result['commits']
    print('{:6} {:4} existing commits'.format('', len(existing_commit_hexsha_list)))

    # get the new commits
    all_commit_list = get_all_commit_list(repo)
    new_commit_list = get_new_commit_list(all_commit_list, existing_commit_hexsha_list)

    print('{:6} {:4} new commits'.format('found', len(new_commit_list)))

    # get file content hashes
    content_hash_list = get_content_hash_list(repo_directory, repo, new_commit_list)

    # save the result if there is a least a new commit
    if len(new_commit_list) > 0:
        # if history has rewritten, keep erased commits
        for content_hash in content_hash_list:
            if content_hash not in result['hashes']:
                result['hashes'].append(content_hash)

        new_commit_hexsha_list = commit_list_to_hexsha_list(new_commit_list)
        result['commits'] = existing_commit_hexsha_list + new_commit_hexsha_list

        # save the result
        save(cache_file, result)

    return set(result['hashes'])


def fetch_file_content_hashes():
    return _fetch_file_content_hashes(get_hashes_file_name(),
                                      get_git_repository_path(SEARX_GIT_REPOSITORY),
                                      SEARX_GIT_REPOSITORY)
