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

0.25.0 (2025-12-20)
===================

Breaking Changes
----------------

- Drop Python 3.9 support and add Python 3.14 support, updating dependencies such as aiohttp (minimum 3.8 to 3.10) and async-timeout (minimum to 5.0) for stdlib TaskGroup and timeout compatibility in Python 3.11+ (#976)
- Replace `**kwargs` with explicit parameters in `DockerContainer.{stop,restart,kill,delete}()` methods, accepting `t` for server-side stop timeout and `timeout` for client-side request timeouts for consistency with other methods covered in the previous PRs #983 and #990; since this is a BREAKING CHANGE for those who have used the `timeout` argument for the `DockerContainer.restart()` method calls, the users should replace it with `t` to keep the intended semantics (#991)


Bug Fixes
---------

- Fix issue authenticating against private registries where the `X-Registry-Auth` header would require URL-safe substitutions. (#941)


New Features
------------

- Add support for Docker context endpoints with TLS, reading configuration from ``~/.docker/contexts/`` and respecting ``DOCKER_CONTEXT`` environment variable and ``SkipTLSVerify`` option. (#811)
- Add SSH protocol support for secure connections to remote Docker instances via "ssh://" URLs with mandatory host key verification (#982)
- Introduce the client-level ``timeout`` configuration which becomes the base timeout configuration while still allowing legacy individual per-API timeouts and merging it into the base timeout.  Now setting individual float (total) timeout per-API call is HIGHLY DISCOURAGED in favor of composable timeouts via stdlib's `asyncio.timeout()` async context manager. (#983)


Miscellaneous
-------------

- Improve the CI workflows to expand the test matrix for aiohttp 3.10/3.13 releases and let tests use the prebuilt artifact to ensure consistency with the release (#980)
- Isolate the docker instance for swarm and service tests via a docker-in-docker compose stack to avoid affecting the user environment (#981)
- Apply the default cooldown period (7 days) to the dependabot configuration (#984)


0.24.0 (2024-11-21)
===================

Features
--------

- Added Python 3.13 support (#927)
- Added timeout parameter for push method (#929)


Bugfixes
--------

- Fix `DockerImages.build()`, `DockerImages.pull()`, `DockerImages.push()` methods' incorrect return type declarations. (#909)


Deprecations and Removals
-------------------------

- Removed Python 3.8 support as it has reached end of life. (#924)


0.23.0 (2024-09-23)
===================

Features
--------

- Introduce a sentinel value to `_do_query()` and its friend methods to allow configuring per-request infinite timeouts instead of always falling back to the session-level default timeout when setting the timeout argument to `None`, and add the timeout arguments to image-related API wrappers (#900)


0.22.2 (2024-07-18)
===================

Bugfixes
--------

- Use ``TYPE_CHECKING`` flag to avoid importing from ``typing_extensions`` at run time (#876)


0.22.1 (2024-07-05)
===================

Bugfixes
--------

- Fix a missing removal of the legacy `AsyncCM` interface usage and update type annotations to avoid this in the future (#874)


0.22.0 (2024-06-26)
===================

NOTICE: This release drops support for Python 3.7 and older. Please upgrade your Python version or keep using prior releases.

Features
--------

- Adds the force parameter to `DockerVolume.delete()` (#690)
- Migrate from setuptools to hatch.  To install the package and all dependencies, use "pip install .[dev,doc]". (#848)


Bugfixes
--------

- Support additional parameters in swarm init (#323)
- Fixes unittests that don't run locally due to deprecations in later versions of Docker. Tested with 26.00, v1.45. (#849)
- Fix never-awaited coroutines of `_AsyncCM` to close when handling errors (#861)


Misc
----

- #850


0.22.0a1 (2024-05-21)
=====================

Features
--------

- Add support for filters when listing networks.
  Add support for filters when listing volumes.
  Add get option for fetching volumes by name or id. (#623)


Improved Documentation
----------------------

- Update the documentation examples to use the modern `asyncio.run()` pattern and initialize `aiodocker.Docker()` instance inside async functions where there is a valid running event loop (#837)


Deprecations and Removals
-------------------------

- Starting container with non-empty request body was deprecated since API v1.22 and removed in v1.24 (#660)


Misc
----

- #621, #748


0.21.0 (2021-07-23)
===================

Bugfixes
--------

- Use ssl_context passed to Docker constructor for creating underlying connection to docker engine. (#536)
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

- Improve the error message when connection is closed by Docker Engine on TCP hijacking. (#424)


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
