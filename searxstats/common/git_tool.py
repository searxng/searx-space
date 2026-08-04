import os
import pathlib
import git


def get_repository(directory, url):
    print(f'Update git repository {url} to {directory}')

    if "::" in url:
        # unsafe URL
        return Exception("unsafe URL")

    # check if directory is a directory
    if not os.path.isdir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
        else:
            raise Exception(directory + ' is not a directory')

    # repository must be public: answer a default username / password
    os.environ['GIT_ASKPASS'] = str(pathlib.Path(os.getcwd(), __file__).parent / 'askpassword.sh')

    # is it a git repository ?
    try:
        repo = git.Repo(directory)
    except Exception as ex:  # pylint: disable=broad-except
        print('* exception', ex)
        repo = None

    if repo is None:
        # it is not a git repository
        print('* clone repository from {}'.format(url))
        repo = git.Repo.clone_from(url, directory)
    else:
        # mirror remote default tip
        repo.remotes.origin.fetch()
        branch = repo.git.rev_parse('--abbrev-ref', 'origin/HEAD').split('/', 1)[-1]
        print('* Use existing git repository, branch=', branch)
        repo.git.checkout('-B', branch, f'origin/{branch}')
        repo.git.clean('-xdf')

    return repo
