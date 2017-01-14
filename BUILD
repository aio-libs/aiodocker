load('//tools/build_rules:pex_rules.bzl', 'pex_library', 'pex_test_library')

pex_library(
    name='aiodocker',
    srcs=glob(['**'], exclude=['tests/**']),
    reqs=['@aiodocker//:requirements']
)

pex_test_library(
    name='unittest',
    srcs=glob(['**']),
    reqs=[
        '@tester//:requirements',
        '@aiodocker//:requirements'
    ]
)
