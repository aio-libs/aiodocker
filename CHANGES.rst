=======
Changes
=======

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://pip.pypa.io/en/latest/development/#adding-a-news-entry
    we named the news folder "changes".

.. towncrier release notes start

0.21.0 (2021-07-23)
===================

Bugfixes
--------

- Use ssl_context passsed to Docker constructor for creating underlying connection to docker engine. (#536)
- Fix an error when attach/exec when container stops before close connection to it. (#608)


0.20.0 (2021-07-21)
===================

Bugfixes
--------

- Accept auth parameter by `run()` method; it allows auto-pulling absent image from private storages. (#295)
- Fix passing of JSON params. (#543)
- Fix issue with unclosed response object in attach/exec. (#604)


0.19.1 (2020-07-09)
===================

Bugfixes
--------

- Fix type annotations for `exec.start()`, `docker.images.pull()`,
  `docker.images.push()`. Respect default arguments again.

0.19.0 (2020-07-07)
===================

Features
--------

- Run mypy checks on the repo in the non-strict mode. (#466)
- Add ``container.rename()`` method. (#458)


Bugfixes
--------

- Changed DockerNetwork.delete() to return True if successful (#464)


0.18.9 (2020-07-07)
===================

Bugfixes
--------

- Fix closing of the task fetching Docker's event stream and make it re-openable after closing (#448)
- Fix type annotations for pull() and push() methods. (#465)


Misc
----

- #442


0.18.8 (2020-05-04)
===================

Bugfixes
--------

- Don't send ``null`` for empty BODY.


0.18.7 (2020-05-04)
===================

Bugfixes
--------

- Fix some typing errors


0.18.1 (2020-04-01)
===================

Bugfixes
--------

- Improve the errror message when connection is closed by Docker Engine on TCP hijacking. (#424)


0.18.0 (2020-03-25)
===================

Features
--------

- Improve the error text message if cannot connect to docker engine. (#411)
- Rename `websocket()` to `attach()` (#412)
- Implement docker exec protocol. (#415)
- Implement container commit, pause and unpause functionality. (#418)
- Implement auto-versioning of the docker API by default. (#419)


Bugfixes
--------

- Fix volume.delete throwing a TypeError. (#389)


0.17.0 (2019-10-15)
===================

Bugfixes
--------

- Fixed an issue when the entire tar archive was stored in RAM while building the image. (#352)


0.16.0 (2019-09-23)
===================

Bugfixes
--------

- Fix streaming mode for pull, push, build, stats and events. (#344)


0.15.0 (2019-09-22)
===================

Features
--------

- Add support for Docker 17.12.1 and 18.03.1 (#164)
- Add initial support for nodes. (#181)
- Add initial support for networks. (#189)
- Add support for docker info ando docker swarm join. (#193)
- Add restart method for containers. (#200)
- Feature: Add support for registry-auth when you create a service. (#215)
- Feature: Add support for docker save and load api methods (#219)
- Pass params to docker events. (#223)
- Add ability to get a Docker network by name or ID. (#279)
- Always close response after processing, make `.logs(..., follow=True)` async iterator. (#341)


Bugfixes
--------

- Fix: Set timeout for docker events to 0 (no timeout) (#115)
- Fix: prevents multiple listener tasks to be created automatically (#116)
- Fix: if container.start() fails user won't get the id of the container (#128)
- Improve logging when docker socket not available. (#155)
- Fix current project version. (#156)
- Fix `update out of sequence.` (#169)
- Remove asserts used to check auth with docker registry. (#172)
- Fix: fix to parse response of docker load method as a json stream (#222)
- Fix: Handle responses with 0 or missing Content-Length (#237)
- Fix: don't remove non-newline whitespace from multiplexed lines (#246)
- Fix docker_context.tar error (#253)


Deprecations and Removals
-------------------------

- docker.images.get has been renamed to docker.images.inspect, remove support for Docker 17.06 (#164)
- Drop Python 3.5 (#338)
- Drop deprecated container.copy() (#339)


Misc
----

- #28, #167, #192, #286
