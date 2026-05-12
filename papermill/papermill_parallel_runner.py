from __future__ import annotations

import hashlib
import json
import shutil
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from threading import Event, RLock
from typing import Any, Callable, Iterable, Mapping, Sequence

import papermill as pm  # type: ignore[import-untyped]

try:
    import pandas as pd  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency for dict-only usage
    pd = None

"""Parallel Papermill notebook runner with restart support.

This module provides :class:`ParallelPapermillRunner`, which executes a
Jupyter notebook for every parameter combination supplied either as a
dict of lists or as a ``pandas.DataFrame``.  Runs are dispatched to a
``ThreadPoolExecutor`` so that up to *workers* notebooks execute
concurrently.  Each run gets its own working directory inside the
project directory, and any auxiliary files listed in *files* are copied
there before execution starts.

Completed runs are persisted to a JSON restart file so that an
interrupted sweep can be resumed without re-executing already-finished
notebooks.

Typical usage::

    runner = ParallelPapermillRunner(
        notebook="analysis.ipynb",
        parameter_variations={"alpha": [0.1, 0.5, 1.0], "n": [10, 10, 10]},
        files=["data.csv"],
        workers=4,
    )
    results = runner.run()
"""

@dataclass(slots=True)
class RunResult:
    """Outcome of a single notebook execution.

    Attributes:
        index: Zero-based position of this run in the variation list.
        signature: SHA-1 hex digest of the serialised parameter dict,
            used to identify already-finished runs in the restart file.
        parameters: The concrete parameter values passed to papermill.
        output_notebook: Absolute path to the executed output notebook.
        work_dir: Working directory created for this run.
        duration_seconds: Wall-clock time of the papermill execution in
            seconds.
        status: Either ``"finished"`` or ``"failed"``.
        error: Traceback string if the notebook raised an exception,
            ``None`` otherwise.
        postprocessing_error: Traceback string if the postprocessing
            callback raised an exception, ``None`` otherwise.
    """
    index: int
    signature: str
    parameters: dict[str, Any]
    output_notebook: Path
    work_dir: Path
    duration_seconds: float
    status: str
    error: str | None = None
    postprocessing_error: str | None = None


class ParallelPapermillRunner:
    """Execute a notebook for every combination of parameters in parallel.

    Args:
        notebook: Path to the template Jupyter notebook.
        parameter_variations: Either a ``dict`` whose values are equal-
            length lists of values, or a ``pandas.DataFrame`` where each
            row represents one parameter set.
        files: Paths of files to copy into each run's working directory
            before execution.  Relative paths are resolved against the
            directory containing *notebook*.
        workers: Number of notebooks to execute concurrently.
        work_root_dir: Root directory for all run sub-directories.  Defaults
            to ``<notebook_parent>/<notebook_stem>_runs``.
        resume: If ``True``, load existing run state from ``log.json``
            in *work_root_dir* and skip already-finished runs.  If ``False``
            (default), start fresh.  Defaults to ``False``.
        postprocessing: Optional callable that receives the
            :class:`RunResult` of each finished notebook.  Errors inside
            the callback are caught and stored in
            :attr:`RunResult.postprocessing_error`.
    """

    def __init__(
        self,
        notebook: str | Path,
        parameter_variations: Mapping[str, Sequence[Any]] | Any,
        files: Sequence[str | Path] | None,
        workers: int,
        work_root_dir: str | Path | None = None,
        resume: bool = False,
        postprocessing: Callable[[RunResult], Any] | None = None,
    ) -> None:
        """Initialise the runner and load any existing restart state if resume=True."""
        if workers < 1:
            raise ValueError("workers must be greater than zero")

        self.input_notebook = Path(notebook).expanduser().resolve()
        if not self.input_notebook.exists():
            raise FileNotFoundError(f"Notebook not found: {self.input_notebook}")

        self.work_root_dir = (
            Path(work_root_dir).expanduser().resolve()
            if work_root_dir is not None
            else self.input_notebook.parent / f"{self.input_notebook.stem}_runs"
        )
        self.work_root_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.work_root_dir / "log.json"

        self.files = [Path(file_path) for file_path in (files or [])]
        self.workers = workers
        self.postprocessing = postprocessing
        self._stop_requested = Event()
        self._restart_lock = RLock()
        self._variations = self._normalize_variations(parameter_variations)
        self._restart_state = self._load_log_state() if resume else {"entries": []}
        self._finished_signatures = {
            entry["signature"]
            for entry in self._restart_state.get("entries", [])
            if entry.get("status") == "finished"
        }

    def request_stop(self) -> None:
        """Signal the submission loop to stop scheduling new runs.

        Already-running notebooks continue until they finish.  Call
        :meth:`run` again (with the same restart file) to complete the
        remaining variations.
        """
        self._stop_requested.set()

    def run(self) -> list[RunResult]:
        """Execute all pending parameter variations and return the results.

        Variations whose signature already appears in the restart file
        with ``status == "finished"`` are skipped automatically.

        Pressing Ctrl+C will stop accepting new jobs but allow running
        jobs to complete normally.  Results are persisted before returning.

        Returns:
            A list of :class:`RunResult` objects sorted by their
            original index, containing only the runs started in *this*
            call.  Already-finished runs from previous calls are not
            included.
        """
        pending_items = [
            (index, parameters)
            for index, parameters in enumerate(self._variations)
            if self._build_signature(parameters) not in self._finished_signatures
        ]

        if not pending_items:
            return []

        completed: dict[int, RunResult] = {}
        pending_iter = iter(pending_items)
        active: dict[Future[RunResult], int] = {}
        interruption_announced = False

        try:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                while len(active) < self.workers:
                    try:
                        index, parameters = next(pending_iter)
                    except StopIteration:
                        break
                    future = executor.submit(self._execute_single, index, parameters)
                    active[future] = index

                while active:
                    if self._stop_requested.is_set() and not interruption_announced:
                        run_ids = self._format_run_ids(active.values())
                        print(f"Execution interrupted. Finishing runs: {run_ids}.")
                        interruption_announced = True

                    done, _ = wait(
                        set(active.keys()),
                        timeout=0.1,
                        return_when=FIRST_COMPLETED,
                    )
                    if not done:
                        continue

                    for future in done:
                        index = active.pop(future)
                        result = future.result()
                        completed[index] = result
                        if result.status == "finished":
                            self._finished_signatures.add(result.signature)
                        if self._stop_requested.is_set():
                            continue
                        try:
                            next_index, next_parameters = next(pending_iter)
                        except StopIteration:
                            continue
                        next_future = executor.submit(
                            self._execute_single,
                            next_index,
                            next_parameters,
                        )
                        active[next_future] = next_index
        except KeyboardInterrupt:
            print("\n\nCtrl+C detected. Stopping new submissions.")
            self.request_stop()
            # Wait for running jobs to complete
            if active:
                run_ids = self._format_run_ids(active.values())
                print(f"Execution interrupted. Finishing runs: {run_ids}.")
                remaining_futures = set(active.keys())
                while remaining_futures:
                    done, remaining_futures = wait(
                        remaining_futures, return_when=FIRST_COMPLETED
                    )
                    for future in done:
                        index = active.pop(future)  # type: ignore[arg-type]
                        try:
                            result = future.result()
                            completed[index] = result
                        except Exception:
                            pass

        return [completed[index] for index in sorted(completed)]

    def _format_run_ids(self, indices: Iterable[int]) -> str:
        """Return comma-separated zero-padded run ids (for example ``0005, 0008``)."""
        return ", ".join(f"{index:04d}" for index in sorted(set(indices)))

    def _execute_single(self, index: int, parameters: dict[str, Any]) -> RunResult:
        """Create the run directory, copy support files, and execute the notebook.

        Automatically persists the result and invokes postprocessing.

        Args:
            index: Position of this variation in the full list.
            parameters: Parameter dict to inject into the notebook.

        Returns:
            A :class:`RunResult` with ``status`` set to either
            ``"finished"`` or ``"failed"``.
        """
        signature = self._build_signature(parameters)
        run_dir = self._build_run_directory(index)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._copy_support_files(run_dir)

        output_notebook = run_dir / self.input_notebook.name
        started_at = time.perf_counter()
        try:
            pm.execute_notebook(
                input_path=str(self.input_notebook),
                output_path=str(output_notebook),
                parameters=parameters,
                cwd=str(run_dir),
                progress_bar=False,
                log_output=False,
            )
            duration_seconds = time.perf_counter() - started_at
            result = RunResult(
                index=index,
                signature=signature,
                parameters=parameters,
                output_notebook=output_notebook,
                work_dir=run_dir,
                duration_seconds=duration_seconds,
                status="finished",
            )
            self._store_result(result)
            self._run_postprocessing(result)
            return result
        except Exception:
            duration_seconds = time.perf_counter() - started_at
            result = RunResult(
                index=index,
                signature=signature,
                parameters=parameters,
                output_notebook=output_notebook,
                work_dir=run_dir,
                duration_seconds=duration_seconds,
                status="failed",
                error=traceback.format_exc(),
            )
            self._store_result(result)
            return result

    def _run_postprocessing(self, result: RunResult) -> None:
        """Invoke the user-supplied postprocessing callback, catching any errors."""
        if self.postprocessing is None:
            return
        try:
            self.postprocessing(result)
        except Exception:
            result.postprocessing_error = traceback.format_exc()
            self._store_result(result)

    def _build_run_directory(self, index: int) -> Path:
        """Return the (not-yet-created) working directory path for one run.

        The path is ``<work_root_dir>/<index>`` where index is formatted
        as four digits from ``0000`` to ``9999``.

        Args:
            index: Position of this variation (must be in range 0..9999).

        Returns:
            Path to the run directory (not yet created).

        Raises:
            ValueError: If index is outside valid range.
        """
        if not 0 <= index <= 9999:
            raise ValueError("index must be in range 0..9999")
        job_name = f"{index:04d}"
        return self.work_root_dir / job_name

    def _copy_support_files(self, run_dir: Path) -> None:
        """Copy every file listed in *self.files* into *run_dir*.

        Relative paths are resolved against the directory containing
        the template notebook.

        Raises:
            FileNotFoundError: If a source file does not exist.
        """
        for file_path in self.files:
            source = file_path if file_path.is_absolute() else (self.input_notebook.parent / file_path)
            source = source.expanduser().resolve()
            if not source.exists():
                raise FileNotFoundError(f"Support file not found: {source}")
            shutil.copy2(source, run_dir / source.name)

    def _store_result(self, result: RunResult) -> None:
        """Upsert *result* into the log file (thread-safe).

        Updates both the on-disk log file and the in-memory restart state.
        """
        with self._restart_lock:
            payload = self._load_log_state()
            entry = self._result_to_payload(result)
            for index, existing in enumerate(payload["entries"]):
                if existing.get("signature") == result.signature and existing.get("index") == result.index:
                    payload["entries"][index] = entry
                    break
            else:
                payload["entries"].append(entry)
            self._write_log_state(payload)
            self._restart_state = payload

    def _load_log_state(self) -> dict[str, Any]:
        """Read and normalise the log file, returning an empty state if absent.

        Handles both legacy format (raw list) and current format (dict with
        "entries" key) for backward compatibility.

        Returns:
            A dict with "entries" key containing the list of run records.
        """
        if self.log_file.exists():
            raw = json.loads(self.log_file.read_text(encoding="utf-8-sig"))
            if isinstance(raw, list):
                return {"entries": raw}
            if isinstance(raw, dict) and "entries" in raw:
                return raw

        return {"entries": []}

    def _write_log_state(self, payload: dict[str, Any]) -> None:
        """Atomically write *payload* to the log file via a temp file.

        Uses a temporary file and rename to ensure the log file is never
        corrupted, even if the write is interrupted.
        """

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.log_file.with_suffix(self.log_file.suffix + ".tmp")
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        with self._restart_lock:
            tmp_file.write_text(text, encoding="utf-8")
            tmp_file.replace(self.log_file)

    def _result_to_payload(self, result: RunResult) -> dict[str, Any]:
        """Serialise a :class:`RunResult` to a JSON-safe dict."""
        work_dir = result.work_dir
        try:
            work_dir_rel = work_dir.relative_to(self.work_root_dir)
            work_dir_value = work_dir_rel.name  # Just the numeric part, e.g. "0000"
        except ValueError:
            work_dir_value = str(work_dir)

        return {
            "index": result.index,
            "signature": result.signature,
            "parameters": self._json_safe(result.parameters),
            "work_dir": work_dir_value,
            "duration_seconds": round(result.duration_seconds, 4),
            "status": result.status,
            "error": result.error,
            "postprocessing_error": result.postprocessing_error,
        }

    def _normalize_variations(
        self,
        parameter_variations: Mapping[str, Sequence[Any]] | Any,
    ) -> list[dict[str, Any]]:
        """Convert *parameter_variations* to a list of parameter dicts.

        Accepts either a ``pandas.DataFrame`` (one row per run) or a
        plain ``dict`` mapping parameter names to equal-length lists of
        values.

        Raises:
            TypeError: If the input is neither a DataFrame nor a Mapping,
                or if a column value is not a sequence.
            ValueError: If the parameter lists have different lengths.
        """
        if pd is not None and isinstance(parameter_variations, pd.DataFrame):
            return [row.to_dict() for _, row in parameter_variations.iterrows()]

        if not isinstance(parameter_variations, Mapping):
            raise TypeError(
                "parameter_variations must be a mapping of lists or a pandas DataFrame",
            )

        if not parameter_variations:
            return [{}]

        columns = list(parameter_variations.keys())
        rows = []
        lengths: set[int] = set()
        normalized_columns: list[list[Any]] = []

        for key in columns:
            values = parameter_variations[key]
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
                raise TypeError(
                    f"Parameter '{key}' must be a sequence of values",
                )
            normalized_values = list(values)
            lengths.add(len(normalized_values))
            normalized_columns.append(normalized_values)

        if len(lengths) > 1:
            raise ValueError("All parameter lists must have the same length")

        for row_values in zip(*normalized_columns, strict=False):
            rows.append(dict(zip(columns, row_values, strict=False)))

        return rows

    def _build_signature(self, parameters: dict[str, Any]) -> str:
        """Return a SHA-1 hex digest that uniquely identifies a parameter set."""
        serialized = json.dumps(self._json_safe(parameters), sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    def _json_safe(self, value: Any) -> Any:
        """Recursively convert *value* to a JSON-serialisable Python object."""
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        if hasattr(value, "item") and callable(value.item):
            try:
                return value.item()
            except Exception:
                return str(value)
        if hasattr(value, "tolist") and callable(value.tolist):
            try:
                return value.tolist()
            except Exception:
                return str(value)
        return value

