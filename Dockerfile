FROM odoo:19

USER root
COPY requirements.txt requirements-test.txt /tmp/test-requirements/
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git libssl-dev python3-dev swig \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        -r /tmp/test-requirements/requirements.txt \
        -r /tmp/test-requirements/requirements-test.txt \
    && rm -rf /var/lib/apt/lists/* /tmp/test-requirements

WORKDIR /mnt/extra-addons
USER odoo
