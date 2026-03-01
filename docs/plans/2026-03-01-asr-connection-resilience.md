# ASR Connection Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `POST /v1/audio/transcriptions` fail gracefully for bad request formats and intermittent upstream failures instead of returning opaque 500 errors.

**Architecture:** Keep current aiohttp endpoint and Gradio upstream flow, but add early request validation, retry logic for transient upstream transport failures, and explicit HTTP error mapping (400/502/504). Add tests against the API handler behavior.

**Tech Stack:** Python 3.10+, aiohttp, gradio_client, unittest (stdlib)

---

### Task 1: Add failing tests for bad content type and upstream failure mapping

**Files:**
- Create: `tests/test_transcriptions.py`
- Modify: `asr2api/__init__.py` (only if needed for testability)

**Step 1: Write failing test**
- Test A: non-multipart request to `/v1/audio/transcriptions` should return 400 JSON error.
- Test B: transient upstream exception during predict should return 502 JSON error instead of uncaught 500.

**Step 2: Run tests to verify fail**
- Run only new tests and confirm at least one fails for expected behavior mismatch.

### Task 2: Implement resilient request handling

**Files:**
- Modify: `asr2api/__init__.py`

**Step 1: Add explicit multipart content-type guard**
- Return `400` with clear message when request is not `multipart/form-data`.

**Step 2: Add upstream retry + timeout wrapping**
- Retry transient upstream transport failures a bounded number of times with short backoff.
- Wrap executor call with timeout and map to `504`.
- Map upstream connection/transport failures to `502`.

**Step 3: Keep success path unchanged**
- Existing successful response shape remains compatible.

### Task 3: Verify and summarize

**Files:**
- Modify: `tests/test_transcriptions.py` (if adjustments needed)

**Step 1: Re-run focused tests**
- Confirm all newly added tests pass.

**Step 2: Report behavior changes**
- Provide exact new error behaviors and impacted files.
