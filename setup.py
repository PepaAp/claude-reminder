#!/usr/bin/env python3
"""Interactive Textual wizard for Claude Reminder hooks."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option

ROOT = Path(__file__).resolve().parent
NOTIFY = ROOT / "notify.py"
SETTINGS = Path.home() / ".claude" / "settings.json"

HOOK_EVENTS = {
    "Notification": "permission_prompt|idle_prompt",
    "PermissionRequest": "",
}

ACTION_INSTALL = "install"
ACTION_UNINSTALL = "uninstall"
ACTION_TEST = "test"
ACTION_QUIT = "quit"


@dataclass
class StatusInfo:
    venv_path: Path | None = None
    venv_error: str | None = None
    settings_error: str | None = None
    installed: set[str] | None = None
    hook_command: str | None = None
    hook_command_error: str | None = None

    @property
    def hook_state(self) -> str:
        if self.settings_error:
            return "unable to load settings"
        if self.installed is None:
            return "unknown"
        if self.installed == set(HOOK_EVENTS):
            return "installed"
        if self.installed:
            missing = ", ".join(sorted(set(HOOK_EVENTS) - self.installed))
            return f"partially installed (missing {missing})"
        return "not installed"

    def render(self) -> str:
        lines = [
            "[bold]Status[/bold]",
            f"Claude settings: {SETTINGS}",
            f"Notify script: {NOTIFY}",
        ]

        if self.venv_error:
            lines.append(f"[red]Virtual environment: {self.venv_error}[/red]")
        else:
            lines.append(f"[green]Virtual environment: {self.venv_path}[/green]")

        if self.settings_error:
            lines.append(f"[red]Hooks: {self.settings_error}[/red]")
        elif self.hook_state == "installed":
            lines.append(f"[green]Hooks: {self.hook_state}[/green]")
        elif self.hook_state.startswith("partially"):
            lines.append(f"[yellow]Hooks: {self.hook_state}[/yellow]")
        else:
            lines.append(f"[yellow]Hooks: {self.hook_state}[/yellow]")

        if self.hook_command:
            lines.append(f"Hook command: {self.hook_command}")
        elif self.hook_command_error:
            lines.append(f"[dim]{self.hook_command_error}[/dim]")

        return "\n".join(lines)


def venv_python() -> Path:
    rel = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    path = ROOT / ".venv" / rel
    if not path.is_file():
        raise FileNotFoundError("Missing .venv. Run ./setup.sh or .\\setup.ps1 first.")
    return path


def hook_command() -> str:
    if not NOTIFY.is_file():
        raise FileNotFoundError(f"notify.py not found: {NOTIFY}")
    return f'"{venv_python()}" "{NOTIFY}"'


def notify_path_from_command(command: str) -> Path | None:
    parts = command.strip().split()
    if len(parts) < 2:
        return None
    candidate = Path(parts[-1].strip('"').strip("'"))
    if candidate.name.lower() != "notify.py":
        return None
    try:
        return candidate.resolve()
    except OSError:
        return None


def is_our_command(command: str) -> bool:
    path = notify_path_from_command(command)
    if path is None:
        return False
    try:
        return path == NOTIFY.resolve()
    except OSError:
        return False


def load_settings() -> dict:
    if not SETTINGS.is_file():
        return {}
    with SETTINGS.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid settings file format: {SETTINGS}")
    return data


def save_settings(settings: dict) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temp.replace(SETTINGS)


def prune_our_hooks(event_hooks: list) -> list:
    kept_entries = []
    for entry in event_hooks:
        if not isinstance(entry, dict):
            kept_entries.append(entry)
            continue

        nested = entry.get("hooks")
        if not isinstance(nested, list):
            kept_entries.append(entry)
            continue

        remaining = [
            hook
            for hook in nested
            if not (
                isinstance(hook, dict)
                and hook.get("type") == "command"
                and isinstance(hook.get("command"), str)
                and is_our_command(hook["command"])
            )
        ]
        if remaining:
            updated = dict(entry)
            updated["hooks"] = remaining
            kept_entries.append(updated)
    return kept_entries


def without_our_hooks(settings: dict) -> dict:
    result = dict(settings)
    hooks = result.get("hooks")
    if not isinstance(hooks, dict):
        result.pop("hooks", None)
        return result

    cleaned = {}
    for name, event_hooks in hooks.items():
        if isinstance(event_hooks, list):
            pruned = prune_our_hooks(event_hooks)
            if pruned:
                cleaned[name] = pruned
        else:
            cleaned[name] = event_hooks

    if cleaned:
        result["hooks"] = cleaned
    else:
        result.pop("hooks", None)
    return result


def add_hook(settings: dict, event: str, matcher: str, command: str) -> dict:
    result = dict(settings)
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        result["hooks"] = hooks

    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        entries = []
        hooks[event] = entries

    payload = {
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command}],
    }

    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("matcher") == matcher:
            entries[index] = payload
            return result

    entries.append(payload)
    return result


def installed_events(settings: dict) -> set[str]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return set()

    found: set[str] = set()
    for event in HOOK_EVENTS:
        for entry in hooks.get(event, []):
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []):
                if (
                    isinstance(hook, dict)
                    and hook.get("type") == "command"
                    and isinstance(hook.get("command"), str)
                    and is_our_command(hook["command"])
                ):
                    found.add(event)
                    break
    return found


def collect_status() -> StatusInfo:
    info = StatusInfo()

    try:
        info.venv_path = venv_python()
    except FileNotFoundError as exc:
        info.venv_error = str(exc)

    try:
        settings = load_settings()
        info.installed = installed_events(settings)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        info.settings_error = str(exc)
        info.installed = set()

    try:
        info.hook_command = hook_command()
    except FileNotFoundError as exc:
        info.hook_command_error = str(exc)

    return info


def install_hooks() -> tuple[bool, str]:
    try:
        command = hook_command()
        settings = load_settings()
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        return False, str(exc)

    settings = without_our_hooks(settings)
    for event, matcher in HOOK_EVENTS.items():
        settings = add_hook(settings, event, matcher, command)

    try:
        save_settings(settings)
    except OSError as exc:
        return False, f"Could not save settings: {exc}"

    return True, "Claude Code hooks installed"


def uninstall_hooks() -> tuple[bool, str]:
    if not SETTINGS.is_file():
        return False, "Settings file does not exist, nothing to remove"

    try:
        settings = load_settings()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return False, str(exc)

    if not installed_events(settings):
        return False, "Claude Reminder hooks are not installed"

    try:
        save_settings(without_our_hooks(settings))
    except OSError as exc:
        return False, f"Could not save settings: {exc}"

    return True, "Claude Reminder hooks removed"


def test_notify() -> tuple[bool, str]:
    try:
        python = venv_python()
    except FileNotFoundError as exc:
        return False, str(exc)

    result = subprocess.run([str(python), str(NOTIFY)], check=False)
    if result.returncode == 0:
        return True, "Test signal sent"
    return False, "ESP32 not found or communication failed"


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        margin: 1 2;
        padding: 1 2;
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
    }

    #question {
        column-span: 2;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="question")
            yield Button("Yes", variant="error", id="yes")
            yield Button("No", variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class SetupApp(App[None]):
    TITLE = "Claude Reminder"
    CSS = """
    Screen {
        layout: vertical;
    }

    #status {
        height: auto;
        max-height: 40%;
        margin: 1 2;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }

    #actions {
        height: 1fr;
        margin: 0 2 1 2;
        border: round $primary;
        background: $panel;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="status")
        yield OptionList(
            Option("Install hooks", id=ACTION_INSTALL),
            Option("Remove hooks", id=ACTION_UNINSTALL),
            None,
            Option("Test notification", id=ACTION_TEST),
            None,
            Option("Quit", id=ACTION_QUIT),
            id="actions",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        self.query_one("#status", Static).update(collect_status().render())

    def confirm(self, message: str, on_result) -> None:
        def handle(confirmed: bool | None) -> None:
            if confirmed:
                on_result()

        self.push_screen(ConfirmScreen(message), handle)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return

        if option_id == ACTION_INSTALL:
            self.handle_install()
        elif option_id == ACTION_UNINSTALL:
            self.handle_uninstall()
        elif option_id == ACTION_TEST:
            self.handle_test()
        elif option_id == ACTION_QUIT:
            self.exit()

    def handle_install(self) -> None:
        status = collect_status()
        if status.installed == set(HOOK_EVENTS):
            self.confirm(
                "Hooks are already installed. Reinstall?",
                self.run_install,
            )
            return
        self.run_install()

    def run_install(self) -> None:
        ok, message = install_hooks()
        self.refresh_status()
        if ok:
            self.notify(message, severity="information", timeout=4)
        else:
            self.notify(message, severity="error", timeout=6)

    def handle_uninstall(self) -> None:
        status = collect_status()
        if not status.installed:
            self.notify("Hooks are not installed", severity="warning", timeout=4)
            return
        self.confirm("Remove hooks?", self.run_uninstall)

    def run_uninstall(self) -> None:
        ok, message = uninstall_hooks()
        self.refresh_status()
        if ok:
            self.notify(message, severity="information", timeout=4)
        else:
            self.notify(
                message,
                severity="warning" if "not installed" in message else "error",
                timeout=6,
            )

    def handle_test(self) -> None:
        ok, message = test_notify()
        if ok:
            self.notify(message, severity="information", timeout=4)
        else:
            self.notify(message, severity="warning", timeout=6)


def main() -> None:
    SetupApp().run()


if __name__ == "__main__":
    main()
