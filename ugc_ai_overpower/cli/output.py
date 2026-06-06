"""Colorized terminal output, progress bars, and ASCII tables (stdlib only)."""

from __future__ import annotations

import shutil
import sys
import time


class Colors:
    """ANSI escape codes for terminal colors."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def colorize(text: str, color: str, bold: bool = False) -> str:
    """Wrap *text* in ANSI color codes. No-op if output is not a TTY."""
    if not sys.stdout.isatty():
        return text
    prefix = color
    if bold:
        prefix += Colors.BOLD
    return f"{prefix}{text}{Colors.RESET}"


def success(text: str) -> str:
    """Green text with ✓ prefix."""
    return colorize("✓ ", Colors.GREEN) + text


def error(text: str) -> str:
    """Red text with ✗ prefix."""
    return colorize("✗ ", Colors.RED) + text


def warning(text: str) -> str:
    """Yellow text with ⚠ prefix."""
    return colorize("⚠ ", Colors.YELLOW) + text


def info(text: str) -> str:
    """Blue text with ℹ prefix."""
    return colorize("ℹ ", Colors.BLUE) + text


def header(text: str) -> str:
    """Bold cyan text inside a box."""
    width = min(len(text) + 4, shutil.get_terminal_size((80, 20)).columns - 2)
    top = "┌" + "─" * (width - 2) + "┐"
    mid = "│ " + text.ljust(width - 4) + " │"
    bot = "└" + "─" * (width - 2) + "┘"
    lines = [top, mid, bot]
    if sys.stdout.isatty():
        lines = [colorize(l, Colors.CYAN, bold=True) for l in lines]
    return "\n".join(lines)


class ProgressBar:
    """Simple terminal progress bar (stdlib only)."""

    def __init__(self, total: int, prefix: str = "", width: int = 40):
        self.total = total if total else 1
        self.prefix = prefix
        self.width = width
        self.n = 0
        self._start = time.time()
        self._finished = False

    def update(self, n: int = 1) -> None:
        """Advance the progress bar by *n* steps."""
        self.n += n
        self._draw()

    def finish(self) -> None:
        """Complete the bar and print a newline."""
        if not self._finished:
            self.n = self.total
            self._draw()
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._finished = True

    def _draw(self) -> None:
        if not sys.stdout.isatty():
            return
        pct = self.n / self.total
        filled = int(self.width * pct)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self._start
        eta = (elapsed / max(self.n, 1)) * (self.total - self.n) if self.n else 0
        sys.stdout.write(
            f"\r{self.prefix} [{bar}] {self.n}/{self.total} "
            f"{pct * 100:5.1f}%  {elapsed:.1f}s"
        )
        if eta:
            sys.stdout.write(f"  ETA {eta:.0f}s")
        sys.stdout.flush()

    def __enter__(self) -> ProgressBar:
        return self

    def __exit__(self, *args) -> None:
        self.finish()


def table(headers: list[str], rows: list[list[str]]) -> str:
    """Render an ASCII table with box-drawing characters.

    >>> print(table(["A","B"], [["1","2"],["3","4"]]))
    """
    if not headers:
        return ""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "─" * (sum(col_widths) + 3 * len(col_widths) - 1)
    lines: list[str] = []
    # Header
    lines.append("┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐")
    hdr = "│" + "│".join(f" {h.center(col_widths[i])} " for i, h in enumerate(headers)) + "│"
    lines.append(hdr)
    lines.append("├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤")
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < len(col_widths):
                cells.append(f" {str(cell).ljust(col_widths[i])} ")
            else:
                cells.append(f" {str(cell)} ")
        lines.append("│" + "│".join(cells) + "│")
    lines.append("└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘")
    return "\n".join(lines)
