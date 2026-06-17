# TODO - Multithread duplicate checking

- [x] Inspect current duplicate dedup sweep logic (already inspected key file).
- [x] Implement multithreading in `validation_engine/services/duplicate_service.py`:
  - [x] Add ThreadPoolExecutor worker(s) to compute canonical decisions in parallel.
  - [x] Keep Mongo writes sequential to avoid race conditions.
  - [x] Add batching/limits to avoid loading unlimited documents into memory.


- [ ] Add configurable worker count via env var (optionally in `validation_engine/config.py`).
- [ ] Run a quick sanity check by executing the dedup sweep entrypoint / relevant script (and/or unit tests).

