#!/usr/bin/env python3
import argparse
import json
import re
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Categorize eval runs and remove validation runs."
    )
    parser.add_argument("outputs", nargs="?", type=Path, default=Path("outputs"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    moved = deleted = 0
    for source in sorted(args.outputs.iterdir()):
        if not source.is_dir():
            continue
        if re.fullmatch(r".+--validate--[0-9a-f]{8}", source.name):
            print(f"remove {source}")
            if not args.dry_run:
                shutil.rmtree(source)
            deleted += 1
            continue

        config_path = next(
            (
                path
                for path in (
                    source / "configs/resolved/eval.json",
                    source / "configs/eval.json",
                )
                if path.is_file()
            ),
            None,
        )
        match = re.search(r"--([0-9a-f]{8})$", source.name)
        if config_path is None or match is None:
            continue

        config = json.loads(config_path.read_text())
        env = config["env"]
        taskset = env["taskset"]["id"]
        environment = f"{env['id']}+{taskset}" if env.get("id") else taskset
        model = config["model"]
        relative = Path(
            environment.replace("/", "--"),
            model.replace("/", "--"),
            match.group(1),
        )
        destination = args.outputs / relative
        if destination.exists():
            raise SystemExit(f"Destination already exists: {destination}")

        print(f"{source} -> {destination}")
        if not args.dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, destination)
            config["run"]["dir"] = str(relative)
            moved_config = destination / config_path.relative_to(source)
            moved_config.write_text(json.dumps(config, indent=2) + "\n")
        moved += 1

    action = "Would move/remove" if args.dry_run else "Moved/removed"
    print(f"{action} {moved} eval run(s) and {deleted} validation run(s).")


if __name__ == "__main__":
    main()
