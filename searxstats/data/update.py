from sqlalchemy.orm import lazyload

from searxstats.database import Commit, Content, Fork, commit_content_table


def insert_content(session, commit_obj, content_hash_list):
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

    # add declared commit <-> content relations
    session.execute(commit_content_table.insert(),
                    [{"commit_id": commit_obj.id, "content_id": content_id[0]}
                        for content_id in content_id_list])


def insert_commit(session, repo_url, commit_sha, commit_date, content_hash_list):
    # get fork_obj
    fork_obj = session.query(Fork)\
                        .where(Fork.git_url == repo_url)\
                        .scalar()
    if fork_obj is None:
        fork_obj = Fork(git_url=repo_url)
        session.add(fork_obj)

    # add / update commit_obj
    # don't load commit_obj.contents
    is_new_commit = False
    commit_obj = session.query(Commit)\
                        .options(lazyload(Commit.contents))\
                        .where(Commit.sha == commit_sha)\
                        .scalar()
    if not commit_obj:
        is_new_commit = True
        commit_obj = Commit(sha=commit_sha, date=commit_date, forks=[fork_obj])
        session.add(commit_obj)
    elif fork_obj not in commit_obj.forks:
        commit_obj.forks.append(fork_obj)
        session.add(commit_obj)

    # add new content_obj
    if is_new_commit:
        insert_content(session, commit_obj, content_hash_list)
