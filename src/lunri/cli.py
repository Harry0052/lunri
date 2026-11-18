"""Command line for the Lunri foundation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lunri import __version__
from lunri.benchmark import load_config, run_benchmark
from lunri.dataset import dataset_path, dumps as dump_dataset, generate, load_dataset, select_split
from lunri.doctor import format_text, report
from lunri.fixture import FixtureError, load_cases, select_cases
from lunri.hardware import detect_hardware, suggest_models
from lunri.hostinfo import detect_host
from lunri.meter import HostMeter, NullMeter
from lunri.ollama import LineMockClient, OllamaClient
from lunri.records import parse_utc, write_record
from lunri.reporting import render_hypotheticals, render_report
from lunri.run import execute_case
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
    parser.error(f"unknown command {args.command}")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lunri",
        description=(
            "Check this computer and extract fields from synthetic invoice text "
            "with a deterministic mock. Reports are labeled SIMULATED. No API key is used."
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
    evaluate.add_argument("--runs-dir", type=Path, default=Path("runs"))
    evaluate.add_argument("--json", action="store_true")

    commands.add_parser("demo", help="print hypothetical break-even examples, labeled HYPOTHETICAL")
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
        client = OllamaClient()
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
