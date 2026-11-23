"""Command line for the Lunri foundation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from lunri import __version__
from lunri.assumptions import load_assumptions
from lunri.benchmark import load_config, run_benchmark
from lunri.contracts import ContractError, check_packaged_checksum, load_fixture_manifest, validate_dataset_bytes
from lunri.dataset import dataset_path, dumps as dump_dataset, generate, load_dataset, select_split
from lunri.doctor import format_text, report
from lunri.fixture import FixtureError, load_cases, select_cases
from lunri.hardware import detect_hardware, suggest_models
from lunri.hostinfo import detect_host
from lunri.meter import HostMeter, NullMeter
from lunri.keystore import SECRET_ENV, SettingsError, delete_provider, settings_path, upsert_provider
from lunri.ollama import LineMockClient, OllamaClient
from lunri.prompt_report import render_prompt_report
from lunri.promptflow import DEMO_MODELS, demo_prompt_path, run_prompt_benchmark, scrub_report
from lunri.providers import ProviderError
from lunri.records import parse_utc, write_record
from lunri.reporting import render_hypotheticals, render_report
from lunri.run import execute_case
from lunri.settings_ui import SettingsUI, public_settings_json
from lunri.strategies import STRATEGIES


def app() -> None:
    """Console-script entry. ``python -m lunri`` uses the same function."""
    raise SystemExit(main())


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "run":
        return _run(args)
    if args.command == "hardware":
        return _hardware(args)
    if args.command == "generate":
        return _generate(args)
    if args.command == "eval":
        return _eval(args)
    if args.command == "demo":
        sys.stdout.write(render_hypotheticals())
        return 0
    if args.command == "fixture":
        return _fixture(args)
    if args.command == "prompt":
        return _prompt(args)
    if args.command == "settings":
        return _settings(args)
    parser.error(f"unknown command {args.command}")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lunri",
        description=(
            "Compare an original prompt with a shorter one, and keep the local invoice benchmark. "
            "Mock mode needs no API key. Estimates are labeled."
        ),
    )
    parser.add_argument("--version", action="version", version=f"lunri {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser(
        "doctor",
        help="check Python, the fixture, the mock, privacy defaults, and run-record writes",
    )
    doctor.add_argument("--runs-dir", type=Path, default=Path("runs"))
    doctor.add_argument("--repo-root", type=Path, default=Path.cwd())
    doctor.add_argument("--json", action="store_true")

    run = commands.add_parser(
        "run",
        help="extract the synthetic invoice texts with the mock and write run records",
    )
    run.add_argument("--case", default=None, help="one case id, such as syn-001")
    run.add_argument(
        "--all",
        action="store_true",
        help="include the malformed-input case as well as the success cases",
    )
    run.add_argument("--model", default="mock")
    run.add_argument("--runs-dir", type=Path, default=Path("runs"))
    run.add_argument("--now", default=None, help="timezone-aware timestamp, such as 2026-11-18T17:00:00Z")
    run.add_argument(
        "--keep-raw-text",
        action="store_true",
        help="store the invoice text on the record. Off by default.",
    )
    run.add_argument("--json", action="store_true")

    hardware = commands.add_parser("hardware", help="show detected chip, RAM, and suggested model tags")
    hardware.add_argument("--system", default=None)
    hardware.add_argument("--machine", default=None)
    hardware.add_argument("--memory-bytes", type=int, default=None)
    hardware.add_argument("--brand", default="")

    generate = commands.add_parser("generate", help="rewrite the synthetic dataset from the fixed seed")
    generate.add_argument("--output", type=Path, default=None)

    evaluate = commands.add_parser("eval", help="compare large, small, and cascade on one split")
    evaluate.add_argument("--backend", choices=("mock", "ollama"), default="mock")
    evaluate.add_argument("--split", choices=("smoke", "dev", "heldout"), default="smoke")
    evaluate.add_argument("--strategy", choices=("all",) + STRATEGIES, default="all")
    evaluate.add_argument("--energy", choices=("off", "powermetrics"), default="off")
    evaluate.add_argument("--base-url", default=None, help="loopback Ollama URL, for tests")
    evaluate.add_argument("--runs-dir", type=Path, default=Path("runs"))
    evaluate.add_argument("--json", action="store_true")

    commands.add_parser("demo", help="print hypothetical break-even examples, labeled HYPOTHETICAL")

    fixture = commands.add_parser("fixture", help="accept or reject a synthetic invoice JSONL file")
    fixture.add_argument("--path", type=Path, default=None)
    fixture.add_argument("--json", action="store_true")

    prompt = commands.add_parser("prompt", help="grade a prompt, rewrite it, and compare models")
    prompt.add_argument("--demo", action="store_true", help="run the packaged redundant prompt with the mock provider")
    prompt.add_argument("--text", default=None, help="prompt text")
    prompt.add_argument("--file", type=Path, default=None, help="read the prompt from a file")
    prompt.add_argument("--provider", default="mock")
    prompt.add_argument("--model", action="append", default=None, help="repeat for each model to compare")
    prompt.add_argument("--grader", default=None, help="mock, or a provider name for a live grader")
    prompt.add_argument("--grader-model", default=None)
    prompt.add_argument("--optimizer", default=None)
    prompt.add_argument("--optimizer-model", default=None)
    prompt.add_argument("--energy-assumption", default=None, help="cited assumption id, or none")
    prompt.add_argument("--input-usd-per-million", type=float, default=None)
    prompt.add_argument("--output-usd-per-million", type=float, default=None)
    prompt.add_argument("--base-url", default=None)
    prompt.add_argument("--timeout", type=float, default=60)
    prompt.add_argument("--runs-dir", type=Path, default=Path("runs"))
    prompt.add_argument("--json", action="store_true")

    settings = commands.add_parser("settings", help="store provider keys on this computer")
    settings_commands = settings.add_subparsers(dest="settings_command", required=True)
    settings_commands.add_parser("path", help="print the local settings file path")
    settings_commands.add_parser("list", help="list saved providers without keys")
    ui = settings_commands.add_parser("ui", help="serve the local settings page on 127.0.0.1")
    ui.add_argument("--port", type=int, default=8765)
    add = settings_commands.add_parser("add", help="save a provider using the LUNRI_API_KEY environment variable")
    add.add_argument("--provider", required=True)
    add.add_argument("--label", required=True)
    add.add_argument("--model", default="")
    add.add_argument("--base-url", default="")
    add.add_argument("--input-usd-per-million", type=float, default=None)
    add.add_argument("--output-usd-per-million", type=float, default=None)
    remove = settings_commands.add_parser("remove", help="delete one saved provider by id")
    remove.add_argument("--id", required=True)
    return parser


def _doctor(args: argparse.Namespace) -> int:
    body = report(args.runs_dir, repo_root=args.repo_root)
    sys.stdout.write(dumps(body) if args.json else format_text(body))
    return 0 if body["ok"] else 2


def _run(args: argparse.Namespace) -> int:
    if args.model != "mock":
        sys.stderr.write(
            f"model {args.model!r} is not implemented. This stage only runs 'mock'.\n"
            "A real Ollama model has to be set up on Harry's Mac. See docs/MACOS.md.\n"
        )
        return 2
    try:
        created_at = parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    try:
        selected = select_cases(load_cases(), case_id=args.case, include_all=args.all)
    except FixtureError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    records = []
    paths = []
    for case in selected:
        record = execute_case(case, created_at=created_at, keep_raw_text=args.keep_raw_text)
        try:
            paths.append(write_record(args.runs_dir, record))
        except OSError as exc:
            sys.stderr.write(f"cannot write run record: {exc}\n")
            return 2
        records.append(record)

    if args.json:
        sys.stdout.write(dumps(records))
    else:
        sys.stdout.write(format_runs(records, paths))
    return 0 if all(record["status"] == "ok" for record in records) else 1


def format_runs(records: list[dict], paths: list[Path]) -> str:
    lines = ["SIMULATED report. Mock responses and energy are not benchmark results."]
    for record, path in zip(records, paths):
        output = record["output"]
        lines.extend(
            [
                f"case {record['case_id']}",
                f"response_label {record['response_label']}",
                f"status {record['status']}",
                f"model {record['model']}",
                f"invoice {_show(output['invoice_number'])}",
                f"total_cents {_show(output['total_cents'])}",
                f"currency {_show(output['currency'])}",
                f"energy_label {record['energy']['label']}",
                "joules " + ("null" if record["energy"]["joules"] is None else str(record["energy"]["joules"])),
                f"record {path}",
            ]
        )
        if record["errors"]:
            lines.append("errors " + "; ".join(record["errors"]))
    failed = sum(record["status"] != "ok" for record in records)
    lines.append(f"cases {len(records)} failed {failed}")
    return "\n".join(lines) + "\n"


def _show(value: object) -> str:
    return "null" if value is None else str(value)


def _hardware(args: argparse.Namespace) -> int:
    if args.system or args.machine or args.memory_bytes is not None:
        host = {
            "machine": args.machine or "unknown",
            "memory_bytes": args.memory_bytes,
            "system": args.system or "unknown",
        }
        host["suggestion"] = suggest_models(
            system=host["system"],
            machine=host["machine"],
            memory_bytes=host["memory_bytes"],
            brand=args.brand,
        )
    else:
        host = detect_hardware()
    suggestion = host["suggestion"]
    sys.stdout.write(
        "\n".join(
            [
                f"system {host['system']}",
                f"machine {host['machine']}",
                f"memory_bytes {host['memory_bytes']}",
                f"chip {suggestion['chip']}",
                f"comparison_ready {str(suggestion['comparison_ready']).lower()}",
                f"pull {', '.join(suggestion['pull']) if suggestion['pull'] else 'none'}",
                f"note {suggestion['note']}",
            ]
        )
        + "\n"
    )
    return 0


def _generate(args: argparse.Namespace) -> int:
    path = args.output if args.output is not None else dataset_path()
    path.write_text(dump_dataset(generate()), encoding="utf-8")
    sys.stdout.write(f"wrote {path}\n")
    return 0


def _eval(args: argparse.Namespace) -> int:
    rows = select_split(load_dataset(), args.split)
    if not rows:
        sys.stderr.write(f"split {args.split} has no rows\n")
        return 2
    config = load_config()
    if args.backend == "ollama":
        client = OllamaClient(args.base_url) if args.base_url else OllamaClient()
        ok, detail = client.ping()
        if not ok:
            sys.stderr.write(
                "real inference NOT YET VERIFIED. "
                f"{detail}. Start Ollama on this Mac and pull the suggested tags. See docs/MACOS.md.\n"
            )
            return 2
        inference = "REAL"
    else:
        client = LineMockClient()
        inference = "SIMULATED"
    if args.energy == "powermetrics":
        meter = HostMeter(enabled=True, system=detect_host()["system"])
    else:
        meter = NullMeter("energy sampling was not requested")
    strategies = STRATEGIES if args.strategy == "all" else (args.strategy,)
    body = run_benchmark(
        rows,
        client,
        meter,
        strategies=strategies,
        config=config,
        backend=args.backend,
        split=args.split,
    )
    body["inference_label"] = inference
    body["host"] = {
        "machine": detect_host()["machine"],
        "system": detect_host()["system"],
    }
    path = args.runs_dir / f"eval-{args.backend}-{args.split}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(body), encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"cannot write report: {exc}\n")
        return 2
    if args.json:
        sys.stdout.write(dumps(body))
    else:
        sys.stdout.write(render_report(body))
        sys.stdout.write(f"report {path}\n")
    return 0


def dumps(body: object) -> str:
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def _fixture(args: argparse.Namespace) -> int:
    path = args.path if args.path is not None else dataset_path()
    try:
        raw = path.read_bytes()
        rows = validate_dataset_bytes(raw)
        if args.path is None:
            check_packaged_checksum(raw, load_fixture_manifest())
    except ContractError as exc:
        sys.stderr.write("fixture rejected\n")
        for error in exc.errors:
            sys.stderr.write(f"{error}\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"fixture rejected\ncannot read {path}: {exc.__class__.__name__}\n")
        return 2
    if args.json:
        sys.stdout.write(dumps({"ok": True, "rows": len(rows)}))
    else:
        sys.stdout.write(f"fixture accepted\nrows {len(rows)}\n")
    return 0


def _prompt(args: argparse.Namespace) -> int:
    try:
        prompt, provider, models, grader, energy = _prompt_choices(args)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    try:
        body = run_prompt_benchmark(
            prompt,
            provider=provider,
            models=models,
            grader=grader,
            grader_model=args.grader_model,
            optimizer=args.optimizer or ("mock" if provider == "mock" else provider),
            optimizer_model=args.optimizer_model,
            energy_assumption=energy,
            input_usd_per_million=args.input_usd_per_million,
            output_usd_per_million=args.output_usd_per_million,
            timeout=args.timeout,
            base_url=args.base_url,
        )
    except (ValueError, ProviderError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    body = scrub_report(body)
    path = args.runs_dir / "prompt-comparison.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(body), encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"cannot write report: {exc.__class__.__name__}\n")
        return 2
    text = render_prompt_report(body)
    sys.stdout.write(dumps(body) if args.json else text)
    if not args.json:
        sys.stdout.write(f"report {path}\n")
    failed = any(not row["original"]["ok"] or not row["optimized"]["ok"] for row in body["models"])
    return 1 if failed else 0


def _prompt_choices(args: argparse.Namespace) -> tuple[str, str, tuple[str, ...], str, str | None]:
    if args.demo:
        prompt = demo_prompt_path().read_text(encoding="utf-8")
        provider = "mock"
        models = DEMO_MODELS
        grader = "mock"
        energy = args.energy_assumption or "a100-output-marginal"
        return prompt, provider, models, grader, energy
    if args.text and args.file:
        raise ValueError("pass either --text or --file")
    if args.file is not None:
        try:
            prompt = args.file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read prompt file: {exc.__class__.__name__}") from exc
    elif args.text is not None:
        prompt = args.text
    else:
        raise ValueError("pass --text, --file, or --demo")
    provider = args.provider
    models = tuple(args.model or ("mock-small",))
    if provider != "mock" and not args.model:
        raise ValueError("pass --model for a live provider")
    grader = args.grader or ("mock" if provider == "mock" else provider)
    energy = args.energy_assumption
    if energy == "none":
        energy = None
    if energy:
        load_assumptions()
    return prompt, provider, models, grader, energy


def _settings(args: argparse.Namespace) -> int:
    if args.settings_command == "path":
        sys.stdout.write(f"{settings_path()}\n")
        return 0
    if args.settings_command == "list":
        try:
            sys.stdout.write(public_settings_json())
        except SettingsError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        return 0
    if args.settings_command == "add":
        key = os.environ.get(SECRET_ENV, "")
        if args.provider != "ollama" and not key:
            sys.stderr.write(
                f"Set {SECRET_ENV} in the environment, or use `lunri settings ui`. "
                "The key is not accepted as a command argument.\n"
            )
            return 2
        try:
            upsert_provider(
                {
                    "api_key": key,
                    "base_url": args.base_url,
                    "input_usd_per_million": args.input_usd_per_million,
                    "label": args.label,
                    "model": args.model,
                    "output_usd_per_million": args.output_usd_per_million,
                    "provider": args.provider,
                }
            )
        except SettingsError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        sys.stdout.write("saved\n")
        sys.stdout.write(public_settings_json())
        return 0
    if args.settings_command == "remove":
        try:
            found = delete_provider(args.id)
        except SettingsError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        if not found:
            sys.stderr.write(f"no saved provider with id {args.id}\n")
            return 2
        sys.stdout.write("removed\n")
        return 0
    if args.settings_command == "ui":
        if args.port < 0 or args.port > 65535:
            sys.stderr.write("port is out of range\n")
            return 2
        ui = SettingsUI()
        try:
            host, port = ui.start(port=args.port)
        except OSError as exc:
            sys.stderr.write(f"cannot listen: {exc.__class__.__name__}\n")
            return 2
        sys.stdout.write(f"settings ui http://{host}:{port}/\n")
        sys.stdout.flush()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            ui.stop()
        return 0
    sys.stderr.write("unknown settings command\n")
    return 2
