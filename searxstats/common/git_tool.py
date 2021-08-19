import os
import pathlib
import git


def get_repository(directory, url):
    print(f'Update git repository {url} to {directory}')

    # check if directory is a directory
    if not os.path.isdir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
        else:
            raise Exception(directory + ' is not a directory')

    # repository must be public: answer a default username / password
    os.environ['GIT_ASKPASS'] = str(pathlib.Path(os.getcwd(), __file__).parent / 'askpassword.sh')

    # is it a git repository ?
    repo = None
    try:
        repo = git.Repo(directory)
        print('* Use existing git repository, branch=', repo.active_branch.name)
    except Exception as ex:  # pylint: disable=no-member
        print('* exception', ex)

    if repo is None:
        # it is not a git repository
        print('* clone repository from {}'.format(url))
        repo = git.Repo.clone_from(url, directory)
    else:
        # it is a git repository
        # clean
        repo.git.reset('--hard')
        repo.git.clean('-xdf')
        # checkout current branch
        repo.git.checkout(repo.heads[0].name)
        # pull
        repo.git.pull()

    return repo
