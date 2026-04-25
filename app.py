import os
import shutil
import subprocess
import threading
import queue
import json
from flask import Flask, Response, request, jsonify
import openpyxl
import openai
import sys
import time
import random
import logging
from typing import Callable, Any, Optional


app = Flask(__name__)

# ------------------------------------------------------------
# !!! WARNING: This is not recommended for production usage !!!
# ------------------------------------------------------------
# من الأفضل تستعمل ENV بدل ما تكتب المفتاح مباشرة
openai.api_key = os.getenv("OPENAI_API_KEY",
                           "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")  # <--- Your key here

import openai_chat_compat

openai_chat_compat.install()

# ===== Retry: إعداد اللوجينغ
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ===== Retry: OpenAI exceptions (SDK 1.x; legacy openai.error was removed)
try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
        APIError as OpenAIAPIError,
    )

    DEFAULT_RETRY_EXCEPTIONS = (
        RateLimitError,
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
    )
except ImportError:  # openai < 1 (unlikely if install() ran)
    from openai import error as openai_error  # type: ignore

    OpenAIAPIError = openai_error.APIError  # type: ignore
    DEFAULT_RETRY_EXCEPTIONS = (
        openai_error.RateLimitError,
        openai_error.ServiceUnavailableError,
        openai_error.APIError,
        openai_error.Timeout,
        openai_error.TryAgain,
    )


def _subprocess_env(env_extra=None):
    """Windows: child Python often uses cp1252 for stdout; emoji in logs then crash unless UTF-8 mode is on."""
    env = os.environ.copy()
    if sys.platform == "win32":
        env.setdefault("PYTHONUTF8", "1")
    if env_extra:
        env.update(env_extra)
    return env


# Child scripts log UTF-8 (emoji, etc.); Windows defaults to cp1252 → UnicodeDecodeError on the pipe.
_SUBPROCESS_STDOUT_KWARGS = {
    "stdout": subprocess.PIPE,
    "stderr": subprocess.STDOUT,
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
    "bufsize": 1,
}


def call_with_retries(
        func: Callable,
        *args,
        max_attempts: Optional[int] = None,  # None => إلى أن ينجح
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.3,
        retry_on_exceptions: tuple = DEFAULT_RETRY_EXCEPTIONS,
        retry_for_statuses: tuple = (500, 502, 503, 504),
        **kwargs,
) -> Any:
    attempt = 0
    delay = initial_delay
    while True:
        attempt += 1
        try:
            logging.info(f"Attempt {attempt} calling {getattr(func, '__name__', str(func))} ...")
            return func(*args, **kwargs)
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "http_status", None)
            is_retry_exc = isinstance(e, retry_on_exceptions) or (
                isinstance(e, OpenAIAPIError)
                and status is not None
                and status in retry_for_statuses
            )
            is_retry_status = (status in retry_for_statuses) if status is not None else False
            logging.warning(f"Attempt {attempt} failed: {type(e).__name__}: {e}")
            if not (is_retry_exc or is_retry_status):
                logging.error("Not configured to retry this error. Raising.")
                raise
            if (max_attempts is not None) and (attempt >= max_attempts):
                logging.error(f"Exceeded max_attempts={max_attempts}. Raising.")
                raise
            # backoff + jitter
            jitter_amt = delay * jitter
            sleep_s = max(0.1, min(delay + random.uniform(-jitter_amt, jitter_amt), max_delay))
            logging.info(f"Sleeping {sleep_s:.2f}s before next attempt.")
            time.sleep(sleep_s)
            delay = min(delay * backoff_factor, max_delay)


def chat_completion_with_retry(messages, model="gpt-4o-mini", **kwargs):
    return call_with_retries(
        openai.ChatCompletion.create,
        model=model,
        messages=messages,
        temperature=kwargs.pop("temperature", 0.7),
        max_attempts=None,  # عاود حتى ينجح
        **kwargs,
    )


PROJECT_FOLDERS = [

    "A1-Pinterest_01",
    "A2-Pinterest_02",
    "A3-Pinterest_03",
    "A4-Pinterest_04",
    "A5-Pinterest_05",
    "A6-Pinterest_06",
    "A7-Pinterest_07",
    "A8-Pinterest_08",
    "A9-Pinterest_09",
    "A10-Pinterest_10",
    "A11-Pinterest_11",
    "A12-Pinterest_12",
    "A13-Pinterest_13",
    "A14-Pinterest_14",
    "A15-Pinterest_15",
    "A16-Pinterest_16",
    "A17-Pinterest_17",
    "A18-Pinterest_18",
    "A19-Pinterest_19",
    "A20-Pinterest_20",
    "A21-Pinterest_21",
    "A22-Pinterest_22",
    "A23-Pinterest_23",
    "A24-Pinterest_24",
    "A25-Pinterest_25",
    "A26-Pinterest_26",
    "A27-Pinterest_27",
    "A28-Pinterest_28",
    "A29-Pinterest_29",
    "A30-Pinterest_30",
    "A31-Pinterest_31",
    "A32-Pinterest_32",
    "A33-Pinterest_33",
    "A34-Pinterest_34",
    "A35-Pinterest_35",
    "A36-Pinterest_36",
    "A37-Pinterest_37",
    "A38-Pinterest_38",
    "A39-Pinterest_39",
    "A40-Pinterest_40",
    "A41-Pinterest_41",
    "A42-Pinterest_42",
    "A43-Pinterest_43",
    "A44-Pinterest_44",
    "A45-Pinterest_45",
    "A46-Pinterest_46",
    "A47-Pinterest_47",
    "A48-Pinterest_48",
    "A49-Pinterest_49",
    "A50-Pinterest_50",
    "B1-Pinterest_51",
    "B2-Pinterest_52",
    "B3-Pinterest_53",
    "B4-Pinterest_54",
    "B5-Pinterest_55",
    "B6-Pinterest_56",
    "B7-Pinterest_57",
    "B8-Pinterest_58",
    "B9-Pinterest_59",
    "B10-Pinterest_60",
    "B11-Pinterest_61",
    "B12-Pinterest_62",
    "B13-Pinterest_63",
    "B14-Pinterest_64",
    "B15-Pinterest_65",
    "B16-Pinterest_66",
    "B17-Pinterest_67",
    "B18-Pinterest_68",
    "B19-Pinterest_69",
    "B20-Pinterest_70",
    "B21-Pinterest_71",
    "B22-Pinterest_72",
    "B23-Pinterest_73",
    "B24-Pinterest_74",
    "B25-Pinterest_75",
    "B26-Pinterest_76",
    "B27-Pinterest_77",
    "B28-Pinterest_78",
    "B29-Pinterest_79",
    "B30-Pinterest_80",
    "B31-Pinterest_81",
    "B32-Pinterest_82",
    "B33-Pinterest_83",
    "B34-Pinterest_84",
    "B35-Pinterest_85",
    "B36-Pinterest_86",
    "B37-Pinterest_87",
    "B38-Pinterest_88",
    "B39-Pinterest_89",
    "B40-Pinterest_90",
    "B41-Pinterest_91",
    "B42-Pinterest_92",
    "B43-Pinterest_93",
    "B44-Pinterest_94",
    "B45-Pinterest_95",
    "B46-Pinterest_96",
    "B47-Pinterest_97",
    "B48-Pinterest_98",
    "B49-Pinterest_99",
    "B50-Pinterest_100",

]

IMAGINE_GROUP1 = [
    "A1-Pinterest_01",
    "A2-Pinterest_02",
    "A3-Pinterest_03",

]

IMAGINE_GROUP2 = [
    "A4-Pinterest_04",
    "A5-Pinterest_05",
    "A6-Pinterest_06",
]

IMAGINE_GROUP3 = [
    "A7-Pinterest_07",
    "A8-Pinterest_08",
    "A9-Pinterest_09",
]

IMAGINE_GROUP4 = [
    "A10-Pinterest_10",
    "A11-Pinterest_11",
    "A12-Pinterest_12",
]

IMAGINE_GROUP5 = [
    "A13-Pinterest_13",
    "A14-Pinterest_14",
    "A15-Pinterest_15",

]

IMAGINE_GROUP6 = [
    "A16-Pinterest_16",
    "A17-Pinterest_17",
    "A18-Pinterest_18",
]

IMAGINE_GROUP7 = [
    "A19-Pinterest_19",
    "A20-Pinterest_20",
    "A21-Pinterest_21",
]

IMAGINE_GROUP8 = [
    "A22-Pinterest_22",
    "A23-Pinterest_23",
    "A24-Pinterest_24",
]

IMAGINE_GROUP9 = [
    "A25-Pinterest_25",
    "A26-Pinterest_26",
    "A27-Pinterest_27",
]

IMAGINE_GROUP10 = [
    "A28-Pinterest_28",
    "A29-Pinterest_29",
    "A30-Pinterest_30",
]

IMAGINE_GROUP11 = [
    "A31-Pinterest_31",
    "A32-Pinterest_32",
    "A33-Pinterest_33",
]

IMAGINE_GROUP12 = [
    "A34-Pinterest_34",
    "A35-Pinterest_35",
    "A36-Pinterest_36",
]

IMAGINE_GROUP13 = [
    "A37-Pinterest_37",
    "A38-Pinterest_38",
    "A39-Pinterest_39",
]

IMAGINE_GROUP14 = [
    "A40-Pinterest_40",
    "A41-Pinterest_41",
    "A42-Pinterest_42",
]

IMAGINE_GROUP15 = [
    "A43-Pinterest_43",
    "A44-Pinterest_44",
    "A45-Pinterest_45",
]

IMAGINE_GROUP16 = [
    "A46-Pinterest_46",
    "A47-Pinterest_47",
    "A48-Pinterest_48",
]

IMAGINE_GROUP17 = [
    "A49-Pinterest_49",
    "A50-Pinterest_50",
]

# -------------------- IMAGINE ALL RANGES (by project index, 1-based) --------------------
# هنا كتتحكم فالمجموعات ديال Imagine All
# (1, 17) = المشاريع من 1 حتى 17 فـ PROJECT_FOLDERS
# (18, 34) = من 18 حتى 34
# (35, 50) = من 35 حتى 50
IMAGINE_ALL_RANGES = [
    (1, 34),
    (35, 50),
    # إلى بغيت تزيد مجموعة أخرى، غير زيد هنا:
    # (51, 60),
]


# -------------------- Specific projects for START2 functionality --------------------
START2_PROJECTS = [
    "B1-Pinterest_51",
    "B2-Pinterest_52",
    "B3-Pinterest_53",
    "B4-Pinterest_54",
    "B5-Pinterest_55",
    "B6-Pinterest_56",
    "B7-Pinterest_57",
    "B8-Pinterest_58",
    "B9-Pinterest_59",
    "B10-Pinterest_60",
    "B11-Pinterest_61",
    "B12-Pinterest_62",
    "B13-Pinterest_63",
    "B14-Pinterest_64",
    "B15-Pinterest_65",
    "B16-Pinterest_66",
    "B17-Pinterest_67",
    "B18-Pinterest_68",
    "B19-Pinterest_69",
    "B20-Pinterest_70",
    "B21-Pinterest_71",
    "B22-Pinterest_72",
    "B23-Pinterest_73",
    "B24-Pinterest_74",
    "B25-Pinterest_75",
    "B26-Pinterest_76",
    "B27-Pinterest_77",
    "B28-Pinterest_78",
    "B29-Pinterest_79",
    "B30-Pinterest_80",
    "B31-Pinterest_81",
    "B32-Pinterest_82",
    "B33-Pinterest_83",
    "B34-Pinterest_84",
    "B35-Pinterest_85",
    "B36-Pinterest_86",
    "B37-Pinterest_87",
    "B38-Pinterest_88",
    "B39-Pinterest_89",
    "B40-Pinterest_90",
    "B41-Pinterest_91",
    "B42-Pinterest_92",
    "B43-Pinterest_93",
    "B44-Pinterest_94",
    "B45-Pinterest_95",
    "B46-Pinterest_96",
    "B47-Pinterest_97",
    "B48-Pinterest_98",
    "B49-Pinterest_99",
    "B50-Pinterest_100",
]

# -------------------- Global list to track running subprocesses --------------------
running_processes = []


# -------------------- 1) Concurrency / SSE Logging --------------------
def generate_log_parallel(script_names, env_extra=None):
    """
    Runs scripts concurrently in separate threads and yields SSE log lines.
    (No concurrency cap)
    """
    q = queue.Queue()
    threads = []
    base_env = _subprocess_env(env_extra)

    def run_process(folder, script):
        folder_abs = os.path.join(os.getcwd(), folder)
        script_path = os.path.join(folder_abs, script)
        if not os.path.exists(script_path):
            q.put({"folder": folder, "line": f"Script {folder}/{script} not found."})
            return
        q.put({"folder": folder, "line": f"Running {folder}/{script}..."})
        if script == "A.4-ARTICLES.py":
            bootstrap = r"""import os, sys, time, random, socket, runpy
        import openai
        _root = os.path.abspath(os.path.join(os.getcwd(), ".."))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        import openai_chat_compat
        openai_chat_compat.install()

        from openai import (
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
            InternalServerError,
            APIError,
        )

        _orig = openai.ChatCompletion.create
        MAX_TRIES = int(os.getenv("OPENAI_RETRY_MAX_TRIES", "6"))
        TIMEOUT = int(os.getenv("OPENAI_REQUEST_TIMEOUT", "180"))

        def _retryable(e):
            if isinstance(e, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError, socket.timeout)):
                return True
            if isinstance(e, APIError):
                code = getattr(e, "status_code", None) or getattr(e, "http_status", None)
                return code in (500, 502, 503, 504)
            return False

        def _create_with_retry(*args, **kwargs):
            if "request_timeout" not in kwargs:
                kwargs["request_timeout"] = TIMEOUT

            for attempt in range(1, MAX_TRIES + 1):
                try:
                    return _orig(*args, **kwargs)
                except Exception as e:
                    if not _retryable(e):
                        raise
                    wait = min(60, (2 ** (attempt - 1)) + random.random())
                    print(f"[OpenAI Retry {attempt}/{MAX_TRIES}] {type(e).__name__}: {e} | waiting {wait:.1f}s...", flush=True)
                    time.sleep(wait)

            raise RuntimeError("OpenAI request failed after multiple retries.")

        openai.ChatCompletion.create = _create_with_retry
        runpy.run_path("A.4-ARTICLES.py", run_name="__main__")
        """
            proc = subprocess.Popen(
                [sys.executable, "-u", "-c", bootstrap],
                cwd=folder_abs,
                env=base_env,
                **_SUBPROCESS_STDOUT_KWARGS,
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, "-u", script],
                cwd=folder_abs,
                env=base_env,
                **_SUBPROCESS_STDOUT_KWARGS,
            )

        running_processes.append(proc)
        for line in proc.stdout:
            q.put({"folder": folder, "line": line.rstrip()})
        proc.stdout.close()
        proc.wait()
        try:
            running_processes.remove(proc)
        except ValueError:
            pass
        q.put({"folder": folder, "line": f"Finished {folder}/{script}"})

    for folder, script in script_names:
        t = threading.Thread(target=run_process, args=(folder, script))
        t.start()
        threads.append(t)

    while any(t.is_alive() for t in threads) or not q.empty():
        try:
            msg = q.get(timeout=0.1)
            yield f"data: {json.dumps(msg)}\n\n"
        except queue.Empty:
            pass

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes."}) + "\n\n"

def generate_log_imagine_all_grouped(env_extra=None):
    """
    Run A.3-IMAGINE.py for ALL projects in GROUPS:
    - المجموعات كيتحددو ف IMAGINE_ALL_RANGES (1-based indices)
    - كل مجموعة كتخدم ف Thread بوحدها (Parallel)
    - داخل كل مجموعة المشاريع كيتخدمو واحد مور واحد (Sequential)
    """
    q = queue.Queue()
    base_env = _subprocess_env(env_extra)

    # نحضرو اللوائح ديال الفولدرات لكل مجموعة
    groups = []
    for i, (start_idx_1, end_idx_1) in enumerate(IMAGINE_ALL_RANGES, start=1):
        # نصححو البدايات والنهايات باش مانخرجوش من PROJECT_FOLDERS
        start_idx_1 = max(1, start_idx_1)
        end_idx_1 = min(len(PROJECT_FOLDERS), end_idx_1)
        if start_idx_1 > end_idx_1:
            continue
        # نحولوه ل 0-based indices
        start0 = start_idx_1 - 1
        end0 = end_idx_1
        folders = PROJECT_FOLDERS[start0:end0]
        if not folders:
            continue
        label = f"Group {i} ({start_idx_1}-{end_idx_1})"
        groups.append((label, folders))

    def run_group(label, folders):
        for folder in folders:
            script = "A.3-IMAGINE.py"
            folder_abs = os.path.join(os.getcwd(), folder)
            script_path = os.path.join(folder_abs, script)
            if not os.path.exists(script_path):
                q.put({"folder": folder, "line": f"[{label}] Script {folder}/{script} not found."})
                continue

            q.put({"folder": folder, "line": f"[{label}] Running {folder}/{script}..."})
            proc = subprocess.Popen(
                [sys.executable, "-u", script],
                cwd=folder_abs,
                env=base_env,
                **_SUBPROCESS_STDOUT_KWARGS,
            )
            running_processes.append(proc)
            for line in proc.stdout:
                q.put({"folder": folder, "line": f"[{label}] " + line.rstrip()})
            proc.stdout.close()
            proc.wait()
            try:
                running_processes.remove(proc)
            except ValueError:
                pass
            q.put({"folder": folder, "line": f"[{label}] Finished {folder}/{script} (exit={proc.returncode})."})

        q.put({"folder": "all", "line": f"[{label}] Finished all projects in this group."})

    threads = []
    for label, folders in groups:
        t = threading.Thread(target=run_group, args=(label, folders), daemon=True)
        t.start()
        threads.append(t)

    # نخرجو اللوغات حتى يساليو جميع الثريدات
    while any(t.is_alive() for t in threads) or not q.empty():
        try:
            msg = q.get(timeout=0.1)
            yield "data: " + json.dumps(msg) + "\n\n"
        except queue.Empty:
            pass

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all IMAGINE ALL groups."}) + "\n\n"


# -------------------- 2) Pool Runner (Fixed-size concurrency) --------------------
def generate_log_pool(script_names, max_concurrency=10, env_extra=None):
    """
    Fixed-size pool: keeps up to max_concurrency running; if one finishes or is SKIPPED,
    immediately starts the next.
    """
    q = queue.Queue()
    lock = threading.Lock()
    scripts_iter = iter(script_names)
    active_threads = []
    base_env = _subprocess_env(env_extra)

    def run_process(folder, script):
        folder_abs = os.path.join(os.getcwd(), folder)
        script_path = os.path.join(folder_abs, script)
        if not os.path.exists(script_path):
            q.put({"folder": folder, "line": f"Script {folder}/{script} not found (SKIPPED)."})
        else:
            q.put({"folder": folder, "line": f"Running {folder}/{script}..."})
            proc = subprocess.Popen(
                [sys.executable, "-u", script],
                cwd=folder_abs,
                env=base_env,
                **_SUBPROCESS_STDOUT_KWARGS,
            )

            running_processes.append(proc)
            for line in proc.stdout:
                q.put({"folder": folder, "line": line.rstrip()})
            proc.stdout.close()
            proc.wait()
            try:
                running_processes.remove(proc)
            except ValueError:
                pass
            q.put({"folder": folder, "line": f"Finished {folder}/{script}"})

        # refill slot
        with lock:
            try:
                next_folder, next_script = next(scripts_iter)
                t = threading.Thread(target=run_process, args=(next_folder, next_script))
                t.start()
                active_threads.append(t)
            except StopIteration:
                pass

    # prime pool
    for _ in range(min(max_concurrency, len(script_names))):
        try:
            folder, script = next(scripts_iter)
            t = threading.Thread(target=run_process, args=(folder, script))
            t.start()
            active_threads.append(t)
        except StopIteration:
            break

    # stream logs
    while any(t.is_alive() for t in active_threads) or not q.empty():
        try:
            msg = q.get(timeout=0.2)
            yield f"data: {json.dumps(msg)}\n\n"
        except queue.Empty:
            pass

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes."}) + "\n\n"


# -------------------- 2b) BATCH Runner (Strict batches: wait for N to finish, then next N) --------------------
def generate_log_in_batches(script_names, batch_size=3, env_extra=None):
    """
    Runs scripts in strict batches of size `batch_size`.
    - Start at most `batch_size` processes.
    - Wait until ALL of them finish.
    - Then start the next batch.
    Streams all stdout/stderr lines via SSE.
    """
    q = queue.Queue()
    base_env = _subprocess_env(env_extra)

    def run_process(folder, script):
        folder_abs = os.path.join(os.getcwd(), folder)
        script_path = os.path.join(folder_abs, script)
        if not os.path.exists(script_path):
            q.put({"folder": folder, "line": f"Script {folder}/{script} not found."})
            return

        q.put({"folder": folder, "line": f"Running {folder}/{script}..."})
        proc = subprocess.Popen(
            [sys.executable, "-u", script],
            cwd=folder_abs,
            env=base_env,
            **_SUBPROCESS_STDOUT_KWARGS,
        )
        # stream output
        for line in proc.stdout:
            q.put({"folder": folder, "line": line.rstrip()})
        proc.stdout.close()
        proc.wait()
        q.put({"folder": folder, "line": f"Finished {folder}/{script} (exit={proc.returncode})."})

    # Helper: chunk list into batches
    def chunked(seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i + n]

    threads = []
    # Process by batches
    for batch in chunked(list(script_names), batch_size):
        # start a batch
        batch_threads = []
        for folder, script in batch:
            t = threading.Thread(target=run_process, args=(folder, script), daemon=True)
            t.start()
            batch_threads.append(t)
            threads.append(t)

        # While this batch is running, keep yielding queue messages
        while any(t.is_alive() for t in batch_threads):
            try:
                msg = q.get(timeout=0.1)
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                pass
        # drain remaining queue lines for this batch
        while True:
            try:
                msg = q.get_nowait()
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                break

    # ensure all threads done
    for t in threads:
        t.join(timeout=0.1)

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes (batched)."}) + "\n\n"


# -------------------- 3) Streaming Endpoints --------------------

@app.route("/stream-all-start")
def stream_all_start():
    scripts_to_run = [(folder, "A.1-START.py") for folder in PROJECT_FOLDERS if folder not in START2_PROJECTS]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")



@app.route("/stream-all-prompt")
def stream_all_prompt():
    scripts_to_run = [(folder, "A.2-PROMPT.py") for folder in PROJECT_FOLDERS]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")

@app.route("/stream-all-json")
def stream_all_json():
    scripts_to_run = [(folder, "A.2-JSON.py") for folder in PROJECT_FOLDERS]

    # باش نعطيك Done X/Y
    total = len(scripts_to_run)

    def gen():
        done = 0
        for chunk in generate_log_in_batches(scripts_to_run, batch_size=5):
            # chunk = "data: {...}\n\n" أو "data: {...}\n\n"
            # كنحسبو "Finished ..." باش نعرفو شحال تسالا
            if '"line": "Finished ' in chunk:
                done += 1
            yield chunk

        yield "data: " + json.dumps({"folder": "all", "line": f"JSON Done {done}/{total}"}) + "\n\n"

    return Response(gen(), mimetype="text/event-stream")

@app.route("/stream-imagine-all")
def stream_imagine_all():
    """
    IMAGINE ALL:
    - كيشغّل A.3-IMAGINE.py على جميع المشاريع ولكن بالمجموعات:
      * كل مجموعة (range) كتخدم ف Thread بوحدها (Parallel).
      * داخل كل مجموعة المشاريع كيتخدمو واحد مور واحد (Sequential).
    - المجموعات كيتحددو من IMAGINE_ALL_RANGES.
    """
    return Response(
        generate_log_imagine_all_grouped(),
        mimetype="text/event-stream"
    )



@app.route("/stream-imagine-group1")
def stream_imagine_group1():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP1]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group2")
def stream_imagine_group2():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP2]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group3")
def stream_imagine_group3():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP3]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group4")
def stream_imagine_group4():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP4]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group5")
def stream_imagine_group5():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP5]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group6")
def stream_imagine_group6():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP6]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group7")
def stream_imagine_group7():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP7]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group8")
def stream_imagine_group8():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP8]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group9")
def stream_imagine_group9():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP9]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group10")
def stream_imagine_group10():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP10]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group11")
def stream_imagine_group11():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP11]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group12")
def stream_imagine_group12():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP12]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group13")
def stream_imagine_group13():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP13]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group14")
def stream_imagine_group14():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP14]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group15")
def stream_imagine_group15():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP15]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group16")
def stream_imagine_group16():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP16]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


@app.route("/stream-imagine-group17")
def stream_imagine_group17():
    scripts_to_run = [(folder, "A.3-IMAGINE.py") for folder in IMAGINE_GROUP17]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


# -------------------- UPDATED: Articles (pool 10 ب 10) --------------------
@app.route("/stream-all-article")
def stream_all_article():
    scripts_to_run = [(folder, "A.4-ARTICLES.py") for folder in PROJECT_FOLDERS]
    return Response(
        generate_log_pool(scripts_to_run, max_concurrency=10),
        mimetype="text/event-stream"
    )


# -------------------- UPDATED: PIN DATA (pool 10 ب 10) + Skip Existing Rows flag --------------------
@app.route("/stream-all-pin-data")
def stream_all_pin_data():
    """
    كنشغل A.5-PIN DATA.py لكل مشروع، ومعاه env PIN_SKIP_EXISTING=1
    باش السكريبت ديال PIN DATA يتخطّى الصفوف العامرة وميرجعش يعاود لها.
    خاصك تزاد سنيبت فـ A.5-PIN DATA.py (أسفل) باش يفعل هاد السلوك.
    """
    scripts_to_run = [(folder, "A.5-PIN DATA.py") for folder in PROJECT_FOLDERS]
    env_extra = {"PIN_SKIP_EXISTING": "1"}
    return Response(
        generate_log_pool(scripts_to_run, max_concurrency=10, env_extra=env_extra),
        mimetype="text/event-stream"
    )


from flask import Response, stream_with_context

from flask import Response, stream_with_context

@app.route("/stream-all-pin-image")
def stream_all_pin_image():
    BATCH_SIZE = 5
    total = len(PROJECT_FOLDERS)

    @stream_with_context
    def stream():
        done = 0
        yield f"data: 🚀 Starting Pin Image for {total} folders (batch={BATCH_SIZE})\n\n"

        for i in range(0, total, BATCH_SIZE):
            batch_folders = PROJECT_FOLDERS[i:i + BATCH_SIZE]
            start = i + 1
            end = i + len(batch_folders)

            yield f"data: 🚀 Batch {start}-{end} / {total}\n\n"

            scripts_to_run = [(folder, "A.6-PIN IMAGES.py") for folder in batch_folders]

            # run this batch
            for line in generate_log_parallel(scripts_to_run):
                # ✅ مهم: فلتر رسالة النهاية ديال generate_log_parallel باش مايتسدّش SSE وسط الخدمة
                if '"folder": "all"' in line and "Finished all processes." in line:
                    continue
                yield line

            done += len(batch_folders)
            yield f"data: ✅ Done {done}/{total}\n\n"

        # ✅ رسالة نهاية واحدة فقط فالأخير
        yield "data: 🎉 ALL PIN IMAGE DONE\n\n"
        yield 'data: {"folder":"all","line":"Finished all processes."}\n\n'

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )



@app.route("/stream-all-pin-bulk")
def stream_all_pin_bulk():
    scripts_to_run = [(folder, "A.8-PIN BULK.py") for folder in PROJECT_FOLDERS]
    return Response(generate_log_parallel(scripts_to_run), mimetype="text/event-stream")


# -------------------- Stream Endpoint for START2 --------------------
@app.route("/stream_start2")
def stream_start2():
    scripts_to_run = [(folder, "A.1-START.py") for folder in START2_PROJECTS]
    return Response(generate_log_parallel(scripts_to_run),mimetype="text/event-stream")


# -------------------- Stream Endpoint for Single Project Actions --------------------
@app.route("/stream-single")
def stream_single():
    """
    Re-trigger a specific action for one project.
    ?project=<project>&action=<action>
    """
    project = request.args.get("project")
    action = request.args.get("action")
    if not project or not action:
        return Response("Missing parameters", status=400)

    action_to_script = {
        "start": "A.1-START.py",
        "json": "A.2-JSON.py",
        "prompt": "A.2-PROMPT.py",
        "imagine": "A.3-IMAGINE.py",
        "article": "A.4-ARTICLES.py",
        "pin_data": "A.5-PIN DATA.py",
        "pin_image": "A.6-PIN IMAGES.py",
        "wp_upload": "A.7-WP UPLOAD.py",
        "pin_bulk": "A.8-PIN BULK.py",
        "start2": "A.1-START.py"
    }
    script = action_to_script.get(action)
    if not script:
        return Response("Invalid action", status=400)

    # single run; هنا بلا env_extra. إذا بغيت skip هنا أيضاً، زِد env_extra={"PIN_SKIP_EXISTING":"1"}
    return Response(generate_log_parallel([(project, script)]), mimetype="text/event-stream")

# -------------------- WP UPLOAD (pool 10 ب 10) --------------------
@app.route("/stream-all-wp-upload")
def stream_all_wp_upload():
    scripts_to_run = [(folder, "A.7-WP UPLOAD.py") for folder in PROJECT_FOLDERS]
    return Response(
        generate_log_pool(scripts_to_run, max_concurrency=10),
        mimetype="text/event-stream"
    )

# -------------------- Endpoint to Stop Running Scripts --------------------
@app.route("/stop_scripts", methods=["POST"])
def stop_scripts():
    global running_processes
    for proc in running_processes[:]:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    running_processes.clear()
    return jsonify({"status": "success", "message": "All running scripts have been stopped."})


# -------------------- 3) Delete 'ALL' Folder --------------------
@app.route("/delete-all-folder", methods=["POST"])
def delete_all_folder():
    folder_path = os.path.join(os.getcwd(), "ALL")
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            return "<h1>'ALL' folder deleted successfully.</h1><a href='/'>Back</a>"
        except Exception as e:
            return f"<h1>Error deleting folder: {e}</h1><a href='/'>Back</a>"
    else:
        return "<h1>'ALL' folder not found.</h1><a href='/'>Back</a>"


# ------------------------------------------------------------------
# 4) Bulk Titles Upload (OpenAI line-by-line, NO JSON from OpenAI)
# ------------------------------------------------------------------

def filter_only_recipes_with_openai(raw_titles):
    """
    Keep ONLY the lines that are actual cooking recipe titles.
    - Do NOT add, rewrite, or translate any titles.
    - Output must be a subset of the INPUT lines (verbatim), one per line.
    - Remove empty lines, URLs, hashtags, @mentions, emails, and generic non-recipe lines.
    - Deduplicate while preserving original order.
    """
    # Quick pre-filter (regex) to remove obvious junk before sending to OpenAI
    import re
    junk_patterns = [
        r'https?://\S+',
        r'www\.\S+',
        r'\b(?:privacy|terms|policy|cookies?|login|signin|register|subscribe|newsletter|about|contact|homepage|copyright)\b',
        r'#\w+',
        r'@\w+',
        r'\b(?:ingredients?|instructions?|directions?|introduction|recipe overview|conclusion|notes?)\b',
        r'^\s*[\-\*\•\·]+\s*$',
        r'^\s*\d+\s*$',
        r'^\s*$'
    ]
    rx = re.compile("|".join(junk_patterns), re.IGNORECASE)

    cleaned = []
    seen = set()
    for line in raw_titles:
        s = line.strip()
        if not s:
            continue
        if rx.search(s):
            continue
        # Very short tokens (likely noise) -> skip
        if len(s) < 4:
            continue
        # Deduplicate (case-insensitive) while preserving original casing
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)

    if not cleaned:
        return []

    # Build OpenAI prompt: strict subset, no rewriting, no additions
    system_msg = (
        "You are a strict filter for cooking recipe titles. "
        "From the user's input lines, return ONLY the lines that are actual cooking recipes. "
        "Do not add new lines, do not rewrite or translate, do not change casing or punctuation. "
        "Output exactly one original input line per line. If none are recipes, return nothing."
    )
    user_payload = "INPUT LINES:\\n" + "\\n".join(cleaned) + "\\n\\nOUTPUT (subset of input, unchanged, one per line):"

    try:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_payload},
        ]
        resp = chat_completion_with_retry(
            messages, model="gpt-4o-mini", temperature=0
        )
        assistant_msg = resp["choices"][0]["message"]["content"].strip()

        # Post-validate: keep only lines that existed in cleaned (verbatim match ignoring trailing spaces)
        valid_set = {c.strip(): True for c in cleaned}
        out = []
        for ln in assistant_msg.splitlines():
            ln2 = ln.strip()
            if not ln2:
                continue
            if ln2 in valid_set:
                out.append(ln2)
        # Final dedupe preserving order
        final = []
        seen2 = set()
        for s in out:
            if s.lower() not in seen2:
                seen2.add(s.lower())
                final.append(s)
        return final
    except Exception as e:
        print("OpenAI filter_only_recipes_with_openai error:", e)
        # Fallback: return the pre-cleaned list
        return cleaned
def filter_titles_with_openai(raw_titles):
    """
    Filter ONLY. Do not rewrite or generate new titles.
    - Input: list of lines (raw_titles)
    - Output: subset of those lines that are valid cooking recipe titles.
    Rules:
      * Keep original text exactly (no rephrasing, no capitalization changes).
      * Preserve the original order of the kept lines.
      * Do NOT add any new lines.
      * Remove lines that are clearly not recipes: URLs, hashtags, social handles, generic section headers
        (e.g., Introduction, Ingredients, Instructions, Conclusion), promotional/legal text (subscribe, privacy,
        login, terms, cookie), non-food content, or anything unrelated to a dish/recipe name.
      * Do NOT deduplicate similar titles; if the same title appears multiple times, keep all occurrences.
    """
    import re

    # Local quick pre-filter for obvious junk
    cleaned = []
    for line in raw_titles:
        t = line.strip()
        if not t:
            continue
        # Drop anything that looks like a link or handle
        if re.search(r'(https?://|www\.|\.com\b|\.net\b|\.org\b|@\w+|#\w+)', t, re.IGNORECASE):
            continue
        cleaned.append(t)

    if not cleaned:
        return []

    system_content = (
        "You are a strict filter. From the provided list of lines, return ONLY the lines that are genuine cooking "
        "recipe TITLES. Do not invent, rewrite, paraphrase, translate, or fix spelling. Only select from the input. "
        "Return the kept titles exactly as-is, one per line, preserving original order. Remove non-recipe lines such as "
        "URLs, hashtags, social handles, section headers (Introduction/Ingredients/Instructions/Conclusion), and generic/promotional/legal text "
        "(subscribe, privacy, login, terms, cookie, comment, rating, share, follow). Do not deduplicate."
    )

    # Put the lines under a clear marker so the model cannot hallucinate extras
    user_content = "INPUT LINES (one per line):\n" + "\n".join(cleaned) + "\n\n" +                    "Return ONLY the subset that are valid cooking recipe titles, EXACTLY as they appear. One per line. No extra text."

    try:
        resp = chat_completion_with_retry(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            model="gpt-4o-mini",
            temperature=0,
        )
        text = resp["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error calling OpenAI API or parsing response:", e)
        # fallback: just do a conservative local filter with heuristics
        heuristics = []
        for t in cleaned:
            if re.search(r'(\brecipe\b|\bchicken\b|\bbeef\b|\bpasta\b|\bcake\b|\bbrownies\b|\bsalad\b|\bsoup\b|\bcasserole\b|\btacos\b|\bpancakes\b|\bair\s*fryer\b|\binstant\s*pot\b|\bcrock\s*pot\b)', t, re.IGNORECASE):
                heuristics.append(t)
        return heuristics if heuristics else cleaned

    # Parse lines; keep order; remove any accidental extras like bullet prefixes
    kept = []
    for line in text.splitlines():
        s = line.strip(" -• ")
        if not s:
            continue
        # Guard again against links
        if re.search(r'(https?://|www\.|\.com\b|\.net\b|\.org\b)', s, re.IGNORECASE):
            continue
        # Only keep if it existed in the cleaned input (exact match)
        if s in cleaned:
            kept.append(s)

    return kept
@app.route("/upload_titles", methods=["POST"])
def upload_titles():
    """
    2-step process:
      1) preview_only=1 -> use filter_titles_with_openai(...) but do NOT save to XLSX; return them for preview
      2) preview_only=0 -> expects final_titles (the user-edited list) to write to XLSX
    """
    preview_only = request.form.get("preview_only", "0")

    # ------------------ Step 1: PREVIEW ------------------
    if preview_only == "1":
        titles_text = request.form.get("titles", "")
        if not titles_text.strip():
            return jsonify({"status": "error", "message": "No titles provided."}), 400

        raw_titles = [line.strip() for line in titles_text.splitlines() if line.strip()]
        if not raw_titles:
            return jsonify({"status": "error", "message": "No valid titles."}), 400

        filtered_titles = filter_titles_with_openai(raw_titles)
        if not filtered_titles:
            return jsonify({"status": "error", "message": "OpenAI returned no valid recipe titles."}), 400

        return jsonify({
            "status": "preview",
            "message": "Preview of filtered titles (not written to XLSX).",
            "filtered_titles": filtered_titles
        })

    # ------------------ Step 2: CONFIRM & WRITE XLSX ------------------
    else:
        final_titles_json = request.form.get("final_titles", "")
        if not final_titles_json.strip():
            return jsonify({"status": "error", "message": "No final titles provided."}), 400

        try:
            final_titles = json.loads(final_titles_json)
        except:
            return jsonify({"status": "error", "message": "Invalid JSON in final_titles."}), 400

        if not isinstance(final_titles, list) or not final_titles:
            return jsonify({"status": "error", "message": "No valid final titles list."}), 400

        starts_folder = os.path.join(os.getcwd(), "STARTS")
        if not os.path.exists(starts_folder):
            return jsonify({"status": "error", "message": "STARTS folder not found."}), 400

        xlsx_files = [
            f for f in os.listdir(starts_folder)
            if f.lower().endswith(".xlsx") and not f.startswith("~$")
        ]
        if not xlsx_files:
            return jsonify({"status": "error", "message": "No XLSX files in STARTS."}), 400

        num_files = len(xlsx_files)

        def split_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i] for i in range(len(lst))],  # simplified; implement as needed

        # توزيع عادل على الملفات
        chunks = [[] for _ in range(num_files)]
        for i, title in enumerate(final_titles):
            chunks[i % num_files].append(title)

        file_counts = {}

        for file_name, chunk in zip(xlsx_files, chunks):
            file_path = os.path.join(starts_folder, file_name)
            try:
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active

                # Clear old data (row 2..end)
                for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
                    for cell in row:
                        cell.value = None

                # Insert the chunk
                for row_num, title in enumerate(chunk, start=2):
                    sheet.cell(row=row_num, column=1, value=title)

                wb.save(file_path)
                file_counts[file_name] = len(chunk)
            except Exception as e:
                return jsonify({"status": "error", "message": f"Error in {file_name}: {e}"}), 500

        return jsonify({
            "status": "success",
            "message": "Final titles uploaded to XLSX files.",
            "total": len(final_titles),
            "counts": file_counts
        })


# ------------------------------------------------------------------
# 5) Clear FAILED Rows  (UPDATED: supports 'statu' AND 'statu_ing')
# ------------------------------------------------------------------
@app.route("/clear_failed", methods=["POST"])
def clear_failed():
    """
    كيمسح أي صف فـ images.xlsx إذا:
      - 'statu' = FAILED أو خاوي
      - أو 'statu_ing' = FAILED أو خاوي
    إذا كاين غير واحد فيهم، خدام. إذا جوج ما كاينينش كيرجع رسالة مناسبة.
    """
    results = {}
    for project in PROJECT_FOLDERS:
        out_folder = f"{project}-out"
        file_path = os.path.join(os.getcwd(), "ALL", out_folder, "images.xlsx")

        if not os.path.exists(file_path):
            results[project] = "File not found"
            continue

        try:
            wb = openpyxl.load_workbook(file_path)
            sheet = wb.active

            # Locate columns (case-insensitive)
            status_col = None
            status_ing_col = None
            for col in range(1, sheet.max_column + 1):
                v = sheet.cell(row=1, column=col).value
                if not v:
                    continue
                name = str(v).strip().lower()
                if name == "statu":
                    status_col = col
                elif name == "statu_ing":
                    status_ing_col = col

            if not status_col and not status_ing_col:
                results[project] = "No 'statu' or 'statu_ing' column"
                continue

            def needs_delete(row_idx: int) -> bool:
                """
                True إذا خاص الصف يتحيد بناءً على واحد من الأعمدة المتوفّرين:
                - 'statu' أو 'statu_ing' : FAILED أو فارغ
                """

                def cell_val(col_idx):
                    if not col_idx:
                        return None
                    raw = sheet.cell(row=row_idx, column=col_idx).value
                    return str(raw).strip() if raw is not None else ""

                v_statu = cell_val(status_col)
                v_statu_ing = cell_val(status_ing_col)

                cond_statu = (v_statu == "" or (isinstance(v_statu, str) and v_statu.upper() == "FAILED"))
                cond_statu_ing = (
                            v_statu_ing == "" or (isinstance(v_statu_ing, str) and v_statu_ing.upper() == "FAILED"))

                # خدم بالـ OR: إذا شي واحد فيهم مطبق، تحيد الصف
                # إلا بغيتها AND بدّل لـ (cond_statu and cond_statu_ing)
                return cond_statu or cond_statu_ing

            removed_count = 0
            for row in range(sheet.max_row, 1, -1):
                if needs_delete(row):
                    sheet.delete_rows(row)
                    removed_count += 1

            wb.save(file_path)
            results[project] = f"Removed {removed_count} rows"
        except Exception as e:
            results[project] = f"Error: {e}"

    return jsonify({"status": "success", "results": results})


# ------------------------------------------------------------------
# 6) Manage Images (UI)
# ------------------------------------------------------------------
@app.route("/manage_images")
def manage_images():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Manage Images | Materio-Like UI</title>
      <!-- Bootstrap 5 + Boxicons -->
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
      <link href="https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css" rel="stylesheet">
      <style>
        body { background-color: #f8f9fd; }
        .materio-sidebar { width: 250px; min-height: 100vh; background-color: #fff; border-right: 1px solid #eceef1; position: fixed; left: 0; top: 0; padding: 20px; }
        .materio-sidebar .sidebar-title { font-size: 1.3rem; font-weight: bold; margin-bottom: 1rem; display: flex; align-items: center; }
        .materio-sidebar .sidebar-title i { font-size: 1.5rem; margin-right: 10px; color: #7367F0; }
        .materio-sidebar ul { list-style: none; padding: 0; }
        .materio-sidebar ul li { margin: 10px 0; }
        .materio-sidebar ul li a { text-decoration: none; color: #626262; font-weight: 500; display: block; padding: 8px 10px; border-radius: 6px; }
        .materio-sidebar ul li a:hover { background-color: #7367F0; color: #fff; }
        .navbar-materio { margin-left: 270px; background-color: #fff; border-bottom: 1px solid #eceef1; height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; position: fixed; width: calc(100% - 270px); top: 0; z-index: 1000; }
        .navbar-materio h5 { margin: 0; }
        .materio-content { margin-left: 270px; padding: 20px; margin-top: 80px; }
        .card-image-table img { max-width: 60px; border-radius: 4px; }
        .table thead th { vertical-align: bottom; }
        .badge-row { font-size: 0.9rem; }
      </style>
    </head>
    <body>
      <div class="materio-sidebar">
        <div class="sidebar-title">
          <i class='bx bxs-component'></i>
          <span>AUTOMATION</span>
        </div>
        <ul>
          <li><a href="/"><i class='bx bx-home-alt'></i> Dashboard</a></li>
          <li><a href="/manage_images"><i class='bx bx-image'></i> Manage Images</a></li>
          <li><a href="/manage_articles"><i class='bx bx-file'></i> Manage Articles</a></li>
          <li><a href="#" onclick="history.back()"><i class='bx bx-left-arrow-alt'></i> Go Back</a></li>
        </ul>
      </div>

      <div class="navbar-materio">
        <h5>Manage Images</h5>
        <div>
          <i class='bx bx-bell' style="font-size: 20px; margin-right: 20px;'></i>
          <i class='bx bx-user-circle' style="font-size: 24px;"></i>
        </div>
      </div>

      <div class="materio-content">
        <div class="row row-cols-1 row-cols-md-2 g-4">
    """

    for project in PROJECT_FOLDERS:
        file_path = os.path.join(os.getcwd(), "ALL", f"{project}-out", "images.xlsx")
        if not os.path.exists(file_path):
            html += f"""
            <div class="col">
              <div class="card h-100 mb-4">
                <div class="card-body">
                  <h4 class="card-title">{project}</h4>
                  <p class="card-text text-danger">images.xlsx not found.</p>
                </div>
              </div>
            </div>
            """
            continue

        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active

        headers = {}
        for col in range(1, sheet.max_column + 1):
            val = sheet.cell(row=1, column=col).value
            if val and val.strip().lower() in ["image_1", "image_2", "image_3", "image_4"]:
                headers[val.strip().lower()] = col

        html += f"""
          <div class="col">
            <div class="card h-100 card-image-table">
              <div class="card-header bg-light">
                <strong>{project}</strong>
              </div>
              <div class="card-body p-0 table-responsive">
                <table class="table table-striped table-hover mb-0 align-middle">
                  <thead class="table-light">
                    <tr>
                      <th style="width: 60px;">Row</th>
                      <th>image_1</th>
                      <th>image_2</th>
                      <th>image_3</th>
                      <th>image_4</th>
                      <th style="width: 80px;">Action</th>
                    </tr>
                  </thead>
                  <tbody>
        """

        for row_idx in range(2, sheet.max_row + 1):
            image_tags = []
            for img_col_name in ["image_1", "image_2", "image_3", "image_4"]:
                col_index = headers.get(img_col_name)
                if col_index:
                    cell_val = sheet.cell(row=row_idx, column=col_index).value
                    if cell_val:
                        image_tags.append(
                            f"<img src='{cell_val}?r={row_idx}_{img_col_name}' alt='{cell_val}' />"
                        )
                    else:
                        image_tags.append("")
                else:
                    image_tags.append("")

            delete_form = f"""
            <form class="delete-form" action="/delete_image_row" method="post" style="display:inline-block;" onsubmit="return deleteImageRow(event, this);">
              <input type="hidden" name="project" value="{project}" />
              <input type="hidden" name="row_number" value="{row_idx}" />
              <button class="btn btn-sm btn-danger" type="submit">Del</button>
            </form>
            """

            html += f"""
            <tr>
              <td><span class="badge bg-secondary badge-row">{row_idx}</span></td>
              <td>{image_tags[0]}</td>
              <td>{image_tags[1]}</td>
              <td>{image_tags[2]}</td>
              <td>{image_tags[3]}</td>
              <td>{delete_form}</td>
            </tr>
            """

        html += f"""
              </tbody>
                </table>
              </div>
              <div class="card-footer"></div>
            </div>
          </div>
        """

    html += """
        </div> <!-- .row -->
      </div> <!-- .materio-content -->

      <script>
        function deleteImageRow(event, form) {
          event.preventDefault();
          fetch(form.action, {
            method: "POST",
            body: new FormData(form)
          })
          .then(response => response.text())
          .then(data => {
            let row = form.closest("tr");
            if(row) { row.remove(); }
          })
          .catch(error => { alert("Error deleting row: " + error); });
          return false;
        }
      </script>

      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html


@app.route("/manage_articles")
def manage_articles():
    cols = [
        "Main Keyword", "Recipe", "image_1", "image_2", "image_3", "image_4",
        "article", "pinterest_title", "pinterest_description",
        "pinterest_image_short_title", "category", "pinterest_image"
    ]

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Manage Articles | Materio-Like UI</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
      <link href="https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css" rel="stylesheet">
      <style>
        body { background-color: #f8f9fd; }
        .materio-sidebar { width: 250px; min-height: 100vh; background: #fff; border-right: 1px solid #eceef1; position: fixed; padding: 20px; }
        .navbar-materio { margin-left:270px; background:#fff; border-bottom:1px solid #eceef1; height:60px; display:flex; align-items:center; justify-content:space-between; padding:0 20px; position:fixed; width:calc(100% - 270px); top:0; }
        .materio-content { margin-left:270px; padding:20px; margin-top:80px; }
        table td, table th { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
      </style>
    </head>
    <body>
      <div class="materio-sidebar">
        <div class="sidebar-title"><i class='bx bxs-component'></i> <strong>AUTOMATION</strong></div>
        <ul class="list-unstyled">
          <li><a href="/"><i class='bx bx-home-alt'></i> Dashboard</a></li>
          <li><a href="/manage_images"><i class='bx bx-image'></i> Manage Images</a></li>
          <li><a href="/manage_articles"><i class='bx bx-file'></i> Manage Articles</a></li>
        </ul>
      </div>
      <div class="navbar-materio">
        <h5>Manage Articles</h5>
        <div><i class='bx bx-user-circle' style="font-size:24px;"></i></div>
      </div>
      <div class="materio-content">
        <div class="mb-3">
          <form action="/delete_all_article_blanks" method="post">
            <button class="btn btn-danger">Remove All Blank Rows from All Projects</button>
          </form>
        </div>
        <div class="row row-cols-1 g-4">
    """

    for project in PROJECT_FOLDERS:
        path = os.path.join(os.getcwd(), "ALL", f"{project}-out", "ARTICLE.xlsx")
        if not os.path.exists(path):
            html += f"""
            <div class="col">
              <div class="card h-100">
                <div class="card-body">
                  <h4 class="card-title">{project}</h4>
                  <p class="text-danger">ARTICLE.xlsx not found.</p>
                </div>
              </div>
            </div>
            """
            continue

        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb.active

        header_map = {}
        for c in range(1, sheet.max_column + 1):
            val = sheet.cell(row=1, column=c).value
            if val and val.strip() in cols:
                header_map[val.strip()] = c

        html += f"""
          <div class="col">
            <div class="card h-100">
              <div class="card-header bg-light"><strong>{project}</strong></div>
              <div class="card-body p-0 table-responsive">
                <table class="table table-hover mb-0">
                  <thead class="table-light"><tr>
        """
        for col in cols:
            html += f"<th title='{col}'>{col}</th>"
        html += "</tr></thead><tbody>"

        for r in range(2, sheet.max_row + 1):
            vals = []
            empty_found = False
            for col in cols:
                col_idx = header_map.get(col)
                v = sheet.cell(row=r, column=col_idx).value if col_idx else None
                if v is None or (isinstance(v, str) and not v.strip()):
                    empty_found = True
                    vals.append("")
                else:
                    vals.append(v)
            row_class = "table-danger" if empty_found else ""
            html += f"<tr class='{row_class}'>"
            for v in vals:
                html += f"<td title='{v}'>{v}</td>"
            html += "</tr>"

        html += f"""
                  </tbody>
                </table>
              </div>
              <div class="card-footer">
                <form action="/delete_article_blanks" method="post" style="display:inline-block;">
                  <input type="hidden" name="project" value="{project}" />
                  <button class="btn btn-sm btn-danger">Remove Blank Rows</button>
                </form>
              </div>
            </div>
          </div>
        """

    html += """
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html


@app.route("/delete_article_blanks", methods=["POST"])
def delete_article_blanks():
    project = request.form.get("project", "")
    cols = [
        "Main Keyword", "Recipe", "image_1", "image_2", "image_3", "image_4",
        "article", "pinterest_title", "pinterest_description",
        "pinterest_image_short_title", "category", "pinterest_image"
    ]
    if project not in PROJECT_FOLDERS:
        return f"<h1>Invalid project: {project}</h1><a href='/manage_articles'>Back</a>"
    path = os.path.join(os.getcwd(), "ALL", f"{project}-out", "ARTICLE.xlsx")
    if not os.path.exists(path):
        return f"<h1>ARTICLE.xlsx not found for {project}</h1><a href='/manage_articles'>Back</a>"

    wb = openpyxl.load_workbook(path)
    sheet = wb.active
    header_map = {}
    for c in range(1, sheet.max_column + 1):
        val = sheet.cell(row=1, column=c).value
        if val and val.strip() in cols:
            header_map[val.strip()] = c

    removed = 0
    for row_idx in range(sheet.max_row, 1, -1):
        if any(
                (sheet.cell(row=row_idx, column=col_idx).value is None or
                 (isinstance(sheet.cell(row=row_idx, column=col_idx).value, str) and not sheet.cell(row=row_idx,
                                                                                                    column=col_idx).value.strip()))
                for col_idx in header_map.values()
        ):
            sheet.delete_rows(row_idx)
            removed += 1
    wb.save(path)
    return f"<h1>Removed {removed} blank rows from {project}</h1><a href='/manage_articles'>Back</a>"


@app.route("/delete_all_article_blanks", methods=["POST"])
def delete_all_article_blanks():
    cols = [
        "Main Keyword", "Recipe", "image_1", "image_2", "image_3", "image_4",
        "article", "pinterest_title", "pinterest_description",
        "pinterest_image_short_title", "category", "pinterest_image"
    ]
    summary = []
    for project in PROJECT_FOLDERS:
        path = os.path.join(os.getcwd(), "ALL", f"{project}-out", "ARTICLE.xlsx")
        if not os.path.exists(path):
            summary.append(f"{project}: file not found")
            continue
        wb = openpyxl.load_workbook(path)
        sheet = wb.active
        header_map = {}
        for c in range(1, sheet.max_column + 1):
            val = sheet.cell(row=1, column=c).value
            if val and val.strip() in cols:
                header_map[val.strip()] = c
        removed = 0
        for row_idx in range(sheet.max_row, 1, -1):
            if any(
                    (sheet.cell(row=row_idx, column=col_idx).value is None or
                     (isinstance(sheet.cell(row=row_idx, column=col_idx).value, str) and not sheet.cell(row=row_idx,
                                                                                                        column=col_idx).value.strip()))
                    for col_idx in header_map.values()
            ):
                sheet.delete_rows(row_idx)
                removed += 1
        wb.save(path)
        summary.append(f"{project}: {removed} removed")
    result = "<h1>Bulk Blank Removal Summary</h1><ul>" + "".join(
        f"<li>{s}</li>" for s in summary) + "</ul><a href='/manage_articles'>Back</a>"
    return result


# -------------------- 7) Delete Image Row --------------------
@app.route("/delete_image_row", methods=["POST"])
def delete_image_row():
    project = request.form.get("project", "")
    row_number_str = request.form.get("row_number", "")

    if not project or not row_number_str:
        return "<h1>Missing project/row_number</h1><a href='/manage_images'>Back</a>"

    if project not in PROJECT_FOLDERS:
        return f"<h1>Invalid project: {project}</h1><a href='/manage_images'>Back</a>"

    try:
        row_number = int(row_number_str)
    except:
        return "<h1>Invalid row_number</h1><a href='/manage_images'>Back</a>"

    file_path = os.path.join(os.getcwd(), "ALL", f"{project}-out", "images.xlsx")
    if not os.path.exists(file_path):
        return f"<h1>images.xlsx not found for {project}</h1><a href='/manage_images'>Back</a>"

    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active

    if 2 <= row_number <= sheet.max_row:
        sheet.delete_rows(row_number, 1)
        wb.save(file_path)
        return f"<h1>Row {row_number} deleted from {project}'s images.xlsx</h1>"
    else:
        return f"<h1>Row {row_number} out of range</h1>"


# -------------------- 8) Main Dashboard Page --------------------
@app.route("/")
def index():
    starts_folder = os.path.join(os.getcwd(), "STARTS")
    if os.path.exists(starts_folder):
        xlsx_files = [f for f in os.listdir(starts_folder) if f.lower().endswith(".xlsx") and not f.startswith("~$")]
        num_xlsx = len(xlsx_files)
    else:
        num_xlsx = 0

    project_folders_json = json.dumps(PROJECT_FOLDERS)

    log_boxes = ""
    for folder in PROJECT_FOLDERS:
        log_boxes += f"""
          <div class="col-lg-6 mb-4">
            <div class="card h-100">
              <div class="card-header">
                <h6 class="mb-0 text-secondary">{folder} Log</h6>
              </div>
              <div class="card-body overflow-auto" style="height:200px;" id="log_{folder}"></div>
              <div class="card-footer">
                <button class="btn btn-sm btn-info project-action" <button class="btn btn-sm btn-primary project-action" onclick="startProjectAction('{folder}', 'start', this)">START</button>
                <button class="btn btn-sm btn-secondary project-action" onclick="startProjectAction('{folder}', 'json', this)">JSON</button>
                <button class="btn btn-sm btn-warning project-action" onclick="startProjectAction('{folder}', 'prompt', this)">PROMPT</button>
                <button class="btn btn-sm btn-info project-action" onclick="startProjectAction('{folder}', 'imagine', this)">IMAGINE</button>
                <button class="btn btn-sm btn-success project-action" onclick="startProjectAction('{folder}', 'article', this)">ARTICLE</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction('{folder}', 'pin_data', this)">PIN DATA</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction('{folder}', 'pin_image', this)">PIN IMAGE</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction('{folder}', 'wp_upload', this)">WP UPLOAD</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction('{folder}', 'pin_bulk', this)">PIN BULK</button>
              </div>
            </div>
          </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Automation Pinterest</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
      <link href="https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css" rel="stylesheet">
      <style>
        body {{
          background-color: #f8f9fd;
        }}
        .materio-sidebar {{
          width: 250px;
          min-height: 100vh;
          background-color: #fff;
          border-right: 1px solid #eceef1;
          position: fixed;
          left: 0;
          top: 0;
          padding: 20px;
        }}
        .materio-sidebar .sidebar-title {{
          font-size: 1.3rem;
          font-weight: bold;
          margin-bottom: 1rem;
          display: flex;
          align-items: center;
        }}
        .materio-sidebar .sidebar-title i {{
          font-size: 1.5rem;
          margin-right: 10px;
          color: #7367F0;
        }}
        .materio-sidebar ul {{
          list-style: none;
          padding: 0;
        }}
        .materio-sidebar ul li {{
          margin: 10px 0;
        }}
        .materio-sidebar ul li a {{
          text-decoration: none;
          color: #626262;
          font-weight: 500;
          display: block;
          padding: 8px 10px;
          border-radius: 6px;
        }}
        .materio-sidebar ul li a:hover {{
          background-color: #7367F0;
          color: #fff;
        }}
        .navbar-materio {{
          margin-left: 270px;
          background-color: #fff;
          border-bottom: 1px solid #eceef1;
          height: 60px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 20px;
          position: fixed;
          width: calc(100% - 270px);
          top: 0;
          z-index: 1000;
        }}
        .navbar-materio h5 {{ margin: 0; }}
        .materio-content {{ margin-left: 270px; padding: 20px; margin-top: 80px; }}
        .number-button {{
          display: inline-block;
          position: relative;
          margin: 5px;
          padding: 10px 20px 10px 50px;
          background-color: #7367F0;
          color: #fff;
          border: none;
          border-radius: 25px;
          cursor: pointer;
          font-size: 14px;
          transition: background-color 0.3s;
          text-decoration: none;
        }}
        .number-button::before {{
          content: attr(data-number);
          position: absolute;
          left: 10px;
          top: 50%;
          transform: translateY(-50%);
          width: 30px;
          height: 30px;
          background-color: #fff;
          color: #7367F0;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
        }}
        .number-button:hover {{ background-color: #5b51db; }}
        .number-button.active {{ background-color: yellow; color: #000; }}
        .number-button.finished {{ background-color: #28c76f; }}
        #previewTable td {{ padding: 5px; vertical-align: middle; }}
        #previewTable button {{ margin-left: 10px; }}
      </style>
      <script>
        var source = null;
        var projectFolders = {project_folders_json};
        var numXlsx = {num_xlsx};

        function disableActionButtons() {{
          var buttons = document.querySelectorAll(".number-button");
          buttons.forEach(function(btn) {{ btn.disabled = true; }});
        }}

        function enableActionButtons() {{
          var buttons = document.querySelectorAll(".number-button");
          buttons.forEach(function(btn) {{ btn.disabled = false; }});
        }}

        function startLog(endpoint, btn) {{
          if(source !== null) {{ return; }}
          disableActionButtons();
          projectFolders.forEach(function(folder) {{
            let div = document.getElementById("log_" + folder);
            if(div) div.innerHTML = "";
          }});

          source = new EventSource(endpoint);
          source.onmessage = function(e) {{
            try {{
              let data = JSON.parse(e.data);
              let folder = data.folder;
              let line = data.line;
              let logDiv = document.getElementById("log_" + folder);
              if(logDiv) {{
                if(line.includes("Finished")) {{
                  logDiv.innerHTML += "<span style='color: green;'>" + line + "</span><br>";
                }} else {{
                  logDiv.innerHTML += line + "<br>";
                }}
                logDiv.scrollTop = logDiv.scrollHeight;
              }}
    if (
      folder === "all" &&
      (
        line.includes("Finished all processes.") ||
        line.includes("Finished all IMAGINE ALL groups.")
      )
    ) {{
      btn.classList.remove("active");
      btn.classList.add("finished");
      enableActionButtons();
      source.close();
      source = null;
    }}

  }} catch (err) {{
    console.error("SSE parse error:", err);
  }}
}};
          source.onerror = function(err) {{
            console.error("EventSource error:", err);
            enableActionButtons();
            source.close();
            source = null;
          }};
          btn.classList.add("active");
        }}

        function stopLog() {{
          if (source) {{
            source.close();
            source = null;
            enableActionButtons();
          }}
          fetch("/stop_scripts", {{ method: "POST" }})
            .then(response => response.json())
            .then(data => {{ console.log("Stopped scripts:", data.message); }})
            .catch(err => {{ console.error("Error stopping scripts:", err); }});
        }}

        function clearFailed() {{
          fetch("/clear_failed", {{ method: "POST" }})
          .then(r => r.json())
          .then(data => {{
            if(data.status === "success") {{
              alert("Clear FAILED done: " + JSON.stringify(data.results));
            }} else {{
              alert("Error: " + data.message);
            }}
          }})
          .catch(err => alert("Error: " + err));
        }}

        document.addEventListener("DOMContentLoaded", function() {{
          let previewForm = document.getElementById("previewForm");
          let previewResult = document.getElementById("previewResult");
          let finalResult = document.getElementById("finalResult");
          let titlesArea = document.getElementById("titles");
          let titleCount = document.getElementById("titleCount");
          let confirmBtn = document.getElementById("confirmBtn");

          if(titlesArea) {{
            titlesArea.addEventListener("input", function() {{
              let lines = titlesArea.value.split(/\\r?\\n/).filter(l => l.trim() !== "");
              let total = lines.length;
              titleCount.innerText = total + " titles";
            }});
          }}

          if(previewForm) {{
            previewForm.addEventListener("submit", function(e) {{
              e.preventDefault();
              previewResult.innerHTML = "Loading preview...";
              finalResult.innerHTML = "";

              let formData = new FormData(previewForm);
              formData.set("preview_only", "1");

              fetch("/upload_titles", {{
                method: "POST",
                body: formData
              }})
              .then(r => r.json())
              .then(data => {{
                if(data.status === "preview") {{
                  const arr = data.filtered_titles;
                  let html = "<table class='table' id='previewTable'><tbody>";
                  for(let i=0; i < arr.length; i++) {{
                    html += "<tr><td>" + arr[i] + "</td>"
                         + "<td><button class='btn btn-sm btn-danger' onclick='removeRow(this)'>Delete</button></td></tr>";
                  }}
                  html += "</tbody></table>";

                  previewResult.innerHTML = html;
                  confirmBtn.style.display = "inline-block";
                }} else {{
                  previewResult.innerHTML = "<span style='color:red'>" + data.message + "</span>";
                  confirmBtn.style.display = "none";
                }}
              }})
              .catch(err => {{
                previewResult.innerHTML = "<span style='color:red'>Error: " + err + "</span>";
                confirmBtn.style.display = "none";
              }});
            }});
          }}

          if(confirmBtn) {{
            confirmBtn.addEventListener("click", function() {{
              finalResult.innerHTML = "Uploading to XLSX...";
              let table = document.getElementById("previewTable");
              if(!table) {{
                finalResult.innerHTML = "<span style='color:red'>No preview table found.</span>";
                return;
              }}
              let rows = table.querySelectorAll("tr");
              let finalTitles = [];
              rows.forEach(r => {{
                let cell = r.querySelector("td");
                if(cell && cell.innerText.trim() !== "") {{
                  finalTitles.push(cell.innerText.trim());
                }}
              }});
              if(finalTitles.length===0) {{
                finalResult.innerHTML = "<span style='color:red'>No titles to upload.</span>";
                return;
              }}

              let formData = new FormData();
              formData.set("preview_only","0");
              formData.set("final_titles", JSON.stringify(finalTitles));

              fetch("/upload_titles", {{
                method: "POST",
                body: formData
              }})
              .then(r => r.json())
              .then(data => {{
                if(data.status==="success") {{
                  finalResult.innerHTML = "<span style='color:green'>" + data.message + "</span>"
                    + "<br>Total: " + data.total
                    + "<br>File distribution: " + JSON.stringify(data.counts);
                }} else {{
                  finalResult.innerHTML = "<span style='color:red'>" + data.message + "</span>";
                }}
              }})
              .catch(err => {{
                finalResult.innerHTML = "<span style='color:red'>Error: " + err + "</span>";
              }});
            }});
          }}
        }});

        function removeRow(btn) {{
          let tr = btn.closest("tr");
          if(tr) tr.remove();
        }}

        var projectStreams = {{}};
        function startProjectAction(project, action, btn) {{
          if(projectStreams[project]) {{ return; }}
          var card = btn.closest('.card');
          var buttons = card.querySelectorAll('button.project-action');
          buttons.forEach(function(b) {{ b.disabled = true; }});
          var endpoint = `/stream-single?project=${{project}}&action=${{action}}`;
          var source = new EventSource(endpoint);
          projectStreams[project] = source;
          source.onmessage = function(e) {{
            try {{
              let data = JSON.parse(e.data);
              let logDiv = document.getElementById("log_" + project);
              if(logDiv) {{
                if(data.line.includes("Finished")) {{
                  logDiv.innerHTML += "<span style='color: green;'>" + data.line + "</span><br>";
                }} else {{
                  logDiv.innerHTML += data.line + "<br>";
                }}
                logDiv.scrollTop = logDiv.scrollHeight;
              }}
              if(data.line.includes("Finished")) {{
                source.close();
                delete projectStreams[project];
                buttons.forEach(function(b) {{ b.disabled = false; }});
              }}
            }} catch(err) {{
              console.error("Project SSE parse error:", err);
            }}
          }};
          source.onerror = function(err) {{
            console.error("Project EventSource error:", err);
            source.close();
            delete projectStreams[project];
            buttons.forEach(function(b) {{ b.disabled = false; }});
          }};
        }}
      </script>
    </head>
    <body>
      <div class="materio-sidebar">
        <div class="sidebar-title">
          <i class='bx bx-grid-alt'></i>
          <span>AUTOMATION</span>
        </div>
        <ul>
          <li><a href="/"><i class='bx bx-home-alt'></i> Dashboard</a></li>
          <li><a href="/manage_images"><i class='bx bx-image'></i> Manage Images</a></li>
          <li><a href="/manage_articles"><i class='bx bx-file'></i> Manage Articles</a></li>
        </ul>
      </div>

      <div class="navbar-materio">
        <h5>Dashboard</h5>
        <div>
          <i class='bx bx-bell' style="font-size: 20px; margin-right: 20px;'></i>
          <i class='bx bx-user-circle' style="font-size: 24px;"></i>
        </div>
      </div>

      <div class="materio-content">
        <div class="card mb-4">
          <div class="card-header">
            <strong>Bulk Recipe Titles - Preview & Review</strong>
          </div>
          <div class="card-body">
            <form id="previewForm" action="/upload_titles" method="post">
              <label for="titles" class="form-label">Enter Titles (one per line)</label>
              <textarea id="titles" name="titles" class="form-control mb-2" rows="3"></textarea>
              <div id="titleCount" class="text-muted mb-2">0 titles</div>
              <button class="btn btn-primary" type="submit">Preview</button>
            </form>
            <div id="previewResult" class="mt-3"></div>
            <button class="btn btn-success mt-3" id="confirmBtn" style="display:none;">Confirm & Upload</button>
            <div id="finalResult" class="mt-3"></div>
          </div>
        </div>

        <div class="card mb-4">
          <div class="card-header">
            <strong>Actions</strong>
          </div>
          <div class="card-body">
            <button class="number-button" data-number="1" onclick="startLog('/stream-all-start', this)">START</button>
            <button class="number-button" data-number="2" onclick="startLog('/stream-all-json', this)">JSON</button>
            <button class="number-button" data-number="2" onclick="startLog('/stream-all-prompt', this)">PROMPT</button>
            <button class="number-button" data-number="ALL" onclick="startLog('/stream-imagine-all', this)">IMAGINE ALL</button>
            <button class="number-button" data-number="3" onclick="startLog('/stream-imagine-group1', this)">IMAGINE 1</button>
            <button class="number-button" data-number="4" onclick="startLog('/stream-imagine-group2', this)">IMAGINE 2</button>
            <button class="number-button" data-number="5" onclick="startLog('/stream-imagine-group3', this)">IMAGINE 3</button>
            <button class="number-button" data-number="6" onclick="startLog('/stream-imagine-group4', this)">IMAGINE 4</button>
            <button class="number-button" data-number="7" onclick="startLog('/stream-imagine-group5', this)">IMAGINE 5</button>
            <button class="number-button" data-number="8" onclick="startLog('/stream-imagine-group6', this)">IMAGINE 6</button>
            <button class="number-button" data-number="9" onclick="startLog('/stream-imagine-group7', this)">IMAGINE 7</button>
            <button class="number-button" data-number="10" onclick="startLog('/stream-imagine-group8', this)">IMAGINE 8</button>
            <button class="number-button" data-number="11" onclick="startLog('/stream-imagine-group9', this)">IMAGINE 9</button>
            <button class="number-button" data-number="12" onclick="startLog('/stream-imagine-group10', this)">IMAGINE 10</button>
            <button class="number-button" data-number="13" onclick="startLog('/stream-imagine-group11', this)">IMAGINE 11</button>
            <button class="number-button" data-number="14" onclick="startLog('/stream-imagine-group12', this)">IMAGINE 12</button>
            <button class="number-button" data-number="15" onclick="startLog('/stream-imagine-group13', this)">IMAGINE 13</button>
            <button class="number-button" data-number="16" onclick="startLog('/stream-imagine-group14', this)">IMAGINE 14</button>
            <button class="number-button" data-number="17" onclick="startLog('/stream-imagine-group15', this)">IMAGINE 15</button>
            <button class="number-button" data-number="18" onclick="startLog('/stream-imagine-group16', this)">IMAGINE 16</button>
            <button class="number-button" data-number="19" onclick="startLog('/stream-imagine-group17', this)">IMAGINE 17</button>
            <button class="number-button" onclick="clearFailed()">CLEAR IMAGINE</button>
            <button class="number-button" data-number="8" onclick="startLog('/stream_start2', this)">START2</button>

            <!-- ARTICLES, PIN DATA, WP UPLOAD: كلهم 10 ب 10 -->
            <button class="number-button" data-number="9" onclick="startLog('/stream-all-article', this)">ARTICLE</button>
            <button class="number-button" data-number="10" onclick="startLog('/stream-all-pin-data', this)">PIN DATA</button>
            <button class="number-button" data-number="11" onclick="startLog('/stream-all-pin-image', this)">PIN IMAGE</button>
            <button class="number-button" data-number="12" onclick="startLog('/stream-all-wp-upload', this)">WP UPLOAD</button>
            <button class="number-button" data-number="13" onclick="startLog('/stream-all-pin-bulk', this)">PIN BULK</button>

            <form action="/delete-all-folder" method="post" style="display:inline-block;">
              <button class="btn btn-secondary ms-2" type="submit">Delete 'ALL'</button>
            </form>
          </div>
        </div>

        <div class="row">
          {log_boxes}
        </div>

      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
# ---- Patch: Ensure IMAGINE ALL button turns green after batches complete ----
try:
    _orig_generate_log_in_batches = generate_log_in_batches
    def generate_log_in_batches(script_names, batch_size=3, env_extra=None):
        for chunk in _orig_generate_log_in_batches(script_names, batch_size=batch_size, env_extra=env_extra):
            yield chunk
        # السطر اللي كيسالي وكيخلي الزرّ يخضر
        yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes."}) + "\n\n"
except NameError:
    pass


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
