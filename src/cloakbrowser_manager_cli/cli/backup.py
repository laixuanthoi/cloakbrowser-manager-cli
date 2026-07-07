"""CLI commands for backing up and restoring manager data."""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import click

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core import database as db


@cli.group()
def backup():
    """Back up and restore manager database/config."""
    pass


@backup.command("create")
@click.option("--out", "out_path", type=click.Path(path_type=Path), help="Output .zip path or directory")
@pass_context
def create_backup(ctx: CLIContext, out_path: Path | None):
    """Create a timestamped zip backup of profiles DB and config."""
    created = _create_backup(out_path)
    if ctx.output.format == "table":
        click.echo(f"Backup created: {created}")
    else:
        ctx.output.print({"backup": str(created)})


@backup.command("list")
@pass_context
def list_backups(ctx: CLIContext):
    """List backups in the default backup directory."""
    backup_dir = _default_backup_dir()
    backups = [
        {"name": p.name, "path": str(p), "size": p.stat().st_size}
        for p in sorted(backup_dir.glob("*.zip"))
    ] if backup_dir.exists() else []
    if ctx.output.format == "table" and not backups:
        click.echo("No backups found.")
        return
    ctx.output.print(backups, title="Backups")


@backup.command("restore")
@click.argument("backup_path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--force", is_flag=True, help="Required to overwrite current DB/config")
@pass_context
def restore_backup(ctx: CLIContext, backup_path: Path, force: bool):
    """Restore DB/config from a backup zip."""
    if not force:
        click.echo("Refusing to overwrite current data without --force", err=True)
        raise SystemExit(1)
    try:
        restored = _restore_backup(backup_path)
    except zipfile.BadZipFile as exc:
        raise click.ClickException(f"Invalid backup archive: {backup_path}") from exc
    except OSError as exc:
        raise click.ClickException(f"Could not restore backup: {exc}") from exc
    if ctx.output.format == "table":
        click.echo(f"Restored backup: {backup_path}")
    else:
        ctx.output.print(restored)


def _default_backup_dir() -> Path:
    return db.get_data_dir() / "backups"


def _create_backup(out_path: Path | None = None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if out_path is None:
        out_path = _default_backup_dir() / f"cloakbrowser-manager-{timestamp}.zip"
    elif out_path.suffix.lower() != ".zip":
        out_path = out_path / f"cloakbrowser-manager-{timestamp}.zip"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    db_path = db.get_db_path()
    config_path = cfg._config_path()  # noqa: SLF001 - internal path helper used for backup/restore

    # Flush WAL content so profiles.db is usable even if sidecar files are absent.
    try:
        with db.get_db() as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:
        pass

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if db_path.exists():
            zf.write(db_path, "profiles.db")
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                zf.write(sidecar, f"profiles.db{suffix}")
        if config_path.exists():
            zf.write(config_path, "config.yaml")
    return out_path


def _restore_backup(backup_path: Path) -> dict[str, str]:
    data_dir = db.get_data_dir()
    config_path = cfg._config_path()  # noqa: SLF001
    restored: dict[str, str] = {}

    with zipfile.ZipFile(backup_path, "r") as zf:
        names = set(zf.namelist())
        if "profiles.db" not in names and "config.yaml" not in names:
            raise click.ClickException("Backup does not contain profiles.db or config.yaml")

        data_dir.mkdir(parents=True, exist_ok=True)
        if "profiles.db" in names:
            target = db.get_db_path()
            for suffix in ("-wal", "-shm"):
                Path(str(target) + suffix).unlink(missing_ok=True)
            _extract_member(zf, "profiles.db", target)
            restored["profiles_db"] = str(target)
            for suffix in ("-wal", "-shm"):
                member = f"profiles.db{suffix}"
                if member in names:
                    sidecar = Path(str(target) + suffix)
                    _extract_member(zf, member, sidecar)
                    restored[member] = str(sidecar)
        if "config.yaml" in names:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            _extract_member(zf, "config.yaml", config_path)
            restored["config"] = str(config_path)
    return restored


def _extract_member(zf: zipfile.ZipFile, member: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)
