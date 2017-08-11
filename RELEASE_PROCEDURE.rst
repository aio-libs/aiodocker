Release Procedure
---------------------

You should have admin access to repo because *master* branch is
protected by GitHub.

Release steps:

1. Make sure that *master* branch is green on travis:
   https://travis-ci.org/aio-libs/aiodocker/branches

2. Switch to *master* branch::

   git checkout master
   git pull

3. TODO: update CHANGES file

4. Open `aiodocker/__init__.py` and edit `__version__` string,
   e.g. replace `'0.10.0a3'` with `'0.10.0'`.

5. Commit changes::

   git add aiodocker/__init__.py
   git commit -m "Bump to 0.10.0"


6. Make a git tag (tag is a version prepended by `v` letter)::

   git tag -a v0.10.0 -m "Release 0.10.0"

7. Push *master* branch and tag onto github::

   git push
   git push origin v0.10.0

8. Travis starts deploying tag automatically. Open travis site
   https://travis-ci.org/aio-libs/aiodocker/branches and wait for end
   of deployment job. It should be green.

9. Open PyPI https://pypi.python.org/pypi/aiodocker and make sure both
   tarball and wheel are uploaded.

   In case of any errors don't override a tag but create new bug fix
   release, e.g. `0.10.1`.

10. Open https://github.com/aio-libs/aiodocker/releases and edit tag
    by adding release description.

    The description highlights significant changes and contains a copy
    of changelog for the release.

11. Edit `__version__` version in `aiodocker/__init__.py` again by
    incrementing release string to point on next alpha, e.g. replace
    `'0.10.0'` with `'0.11.0a0'`.

12. Commit `__init__.py` changes and push the commit to github.

13. Done.