=============
Low-level API
=============

The main object-orientated API is built on top of :py:class:`APIClient`. Each method on :py:class:`APIClient` maps one-to-one with a REST API endpoint, and returns the response that the API responds with.

It's possible to use :py:class:`APIClient` directly. Some basic things (e.g. running a container) consist of several API calls and are complex to do with the low-level API, but it's useful if you need extra flexibility and power.


.. py:module:: aiodocker.api

.. autoclass:: aiodocker.api.APIClient
        :members:
        :undoc-members:

.. _low-level-containers:

Containers
----------

.. py:module:: aiodocker.api.container

.. rst-class:: hide-signature
.. autoclass:: DockerContainerAPI
  :members:
  :undoc-members:

.. _low-level-images:

Images
------

.. py:module:: aiodocker.api.image

.. rst-class:: hide-signature
.. autoclass:: DockerImageAPI
  :members:
  :undoc-members:
