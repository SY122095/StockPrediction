"""可視化スタイル適用 (Analytics notebook 用)

Analytics/configs/visualize.yaml を読み込み、matplotlib/seaborn のスタイルを一括適用する。
"""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from .data_loader import load_yaml

_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "visualize.yaml"

_OS_FONT_KEY = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}


def load_visualize_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or _CONFIG_PATH)


def apply_style(config: dict[str, Any] | None = None, use_japanize: bool = True) -> dict[str, Any]:
    """visualize.yaml の設定を matplotlib/seaborn に適用する。

    use_japanize=True の場合は japanize_matplotlib を優先し (import 副作用で日本語フォント適用)、
    未インストール時は OS別フォント名 (config の font.family) にフォールバックする。
    戻り値はテーマ別フォントサイズ辞書 (title_size/axis_size/tick_size)。
    """
    if config is None:
        config = load_visualize_config()

    viz = config.get("visualization", {})
    mpl_cfg = viz.get("matplotlib", {})

    fig_cfg = mpl_cfg.get("figure", {})
    plt.rcParams["figure.figsize"] = fig_cfg.get("figsize", [12, 6])
    plt.rcParams["figure.dpi"] = fig_cfg.get("dpi", 150)
    plt.rcParams["figure.facecolor"] = fig_cfg.get("facecolor", "white")

    axes_cfg = mpl_cfg.get("axes", {})
    plt.rcParams["axes.labelsize"] = axes_cfg.get("labelsize", 14)
    plt.rcParams["axes.titlesize"] = axes_cfg.get("titlesize", 16)
    plt.rcParams["axes.grid"] = axes_cfg.get("grid", True)
    plt.rcParams["axes.unicode_minus"] = axes_cfg.get("unicode_minus", False)

    grid_cfg = mpl_cfg.get("grid", {})
    plt.rcParams["grid.alpha"] = grid_cfg.get("alpha", 0.3)
    plt.rcParams["grid.linestyle"] = grid_cfg.get("linestyle", "--")

    lines_cfg = mpl_cfg.get("lines", {})
    plt.rcParams["lines.linewidth"] = lines_cfg.get("linewidth", 2)
    plt.rcParams["lines.markersize"] = lines_cfg.get("markersize", 8)

    legend_cfg = mpl_cfg.get("legend", {})
    plt.rcParams["legend.fontsize"] = legend_cfg.get("fontsize", 12)
    plt.rcParams["legend.frameon"] = legend_cfg.get("frameon", False)

    if use_japanize:
        try:
            import japanize_matplotlib  # noqa: F401
        except ImportError:
            font_cfg = mpl_cfg.get("font", {})
            os_key = _OS_FONT_KEY.get(platform.system(), "linux")
            family = font_cfg.get("family", {}).get(os_key)
            if family:
                plt.rcParams["font.family"] = family

    theme_name = viz.get("theme", "notebook")
    return config.get("theme", {}).get(theme_name, {"title_size": 18, "axis_size": 14, "tick_size": 10})


def get_palette(config: dict[str, Any] | None = None) -> dict[str, Any]:
    if config is None:
        config = load_visualize_config()
    return config.get("palette", {})
