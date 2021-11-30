echo run:
docker run -d \
	--name aiodocker-test-registry \
	-p 5000:5000 registry:2

echo run:
docker run -d \
	-p 5001:5001 \
	--name aiodocker-test-registry2 \
	-v `pwd`/tests/certs:/certs \
	-e "REGISTRY_AUTH=htpasswd" \
	-e "REGISTRY_AUTH_HTPASSWD_REALM=Registry Realm" \
	-e REGISTRY_AUTH_HTPASSWD_PATH=/certs/htpasswd \
	-e REGISTRY_HTTP_ADDR=0.0.0.0:5001 \
	-e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/registry.crt \
	-e REGISTRY_HTTP_TLS_KEY=/certs/registry.key registry:2

# this assumes you are in venv.
python3 -m pytest $@

echo delete:
docker rm -f aiodocker-test-registry
echo delete:
docker rm -f aiodocker-test-registry2
