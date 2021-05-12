import os
import git
import git.exc


def get_repository(directory, url):
    print(f'Update git repository {url} to {directory}')

    # check if directory is a directory
    if not os.path.isdir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
        else:
            raise Exception(directory + ' is not a directory')

    # is it a git repository ?
    repo = None
    try:
        repo = git.Repo(directory)
        print('* Use existing git repository')

    except git.exc.GitError as ex:  # pylint: disable=no-member
        print('* exception', ex)

    if repo is None:
        # it is not a git repository
        print('* clone repository from {}'.format(url))
        repo = git.Repo.clone_from(url, directory)
    else:
        # it is a git repository
        # so pull the master branch without additional files
        repo.git.reset('--hard')
        repo.git.clean('-xdf')
        repo.git.checkout('master')
        repo.git.pull()

    return repo
