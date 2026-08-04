Added the ``one_shot`` parameter to ``DockerContainer.stats()``, allowing a single immediate stats sample (Docker API 1.41+) instead of waiting ~1 s for the daemon's two-sample collection.
