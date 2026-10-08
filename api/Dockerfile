FROM python:3.13-slim

WORKDIR /app

# MPLCONFIGDIR: compose runs this as the host UID, which has no home directory
# inside the image; matplotlib otherwise warns on every import.
ENV PYTHONUNBUFFERED=1 \
	HDF5_USE_FILE_LOCKING=FALSE \
	MPLBACKEND=Agg \
	MPLCONFIGDIR=/tmp/matplotlib

RUN pip install --no-cache-dir uv

# The lock, not requirements.txt: a `--build` on the production box must install
# what was tested, not whatever resolves that day.
COPY api/requirements.lock ./
RUN uv pip install --system -r requirements.lock

COPY api .
COPY shared ./shared

# docker-compose may pass a host UID via `user:`; keep /app writable for it.
RUN chmod -R a+rwX /app

EXPOSE 4000

CMD ["uvicorn", "SERVER:app", "--host", "0.0.0.0", "--port", "4000"]
