#!/usr/bin/env python3
"""kashiya-kit: 築古戸建て「現況有姿・格安・DIY可」賃貸の書面ジェネレータ。

使い方:
    python3 build.py config/property_001.yaml

config のYAMLを templates/ のJinja2雛形に流し込み、
output/<config名>/ に Markdown原本と A4印刷用HTML を生成する。

安全装置:
- 個人連帯保証で極度額が未記入ならエラー(民法465条の2: 定めがないと保証契約が無効)
- ハザード情報(土砂災害・浸水)が未記入ならエラー(説明すべき事項のため)
- 実物件configとoutput/がgitで追跡されそうな場合はエラー(個人情報保護)
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

KIT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = KIT_DIR / "templates"
OUTPUT_DIR = KIT_DIR / "output"

GUARANTEE_TYPES = {"保証会社", "連帯保証人", "併用"}
CONTRACT_TYPES = {"定期借家", "普通借家"}
HOT_WATER_UNIT = {"設備", "残置物", "なし"}


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"警告: {msg}", file=sys.stderr)


def get(cfg: dict, path: str, required: bool = True, default=None):
    cur = cfg
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            if required:
                die(f"config に {path} がありません")
            return default
        cur = cur[key]
    if required and cur is None:
        die(f"config の {path} が未記入です")
    return cur


def validate(cfg: dict) -> None:
    for path in [
        "property.name", "property.address", "property.structure",
        "property.built_year", "property.buildings",
        "contract.type", "contract.rent_yen", "contract.deposit_yen",
        "contract.term_years", "contract.cancel_notice_days",
        "contract.guarantee.type",
        "utilities.hot_water", "utilities.water", "utilities.drainage",
    ]:
        get(cfg, path)

    if get(cfg, "contract.type") not in CONTRACT_TYPES:
        die(f"contract.type は {CONTRACT_TYPES} のいずれかにしてください")

    # 保証: 個人根保証の極度額チェック(民法465条の2)
    g_type = get(cfg, "contract.guarantee.type")
    if g_type not in GUARANTEE_TYPES:
        die(f"contract.guarantee.type は {GUARANTEE_TYPES} のいずれかにしてください")
    if g_type in ("連帯保証人", "併用"):
        gokudo = get(cfg, "contract.guarantee.gokudogaku_yen", required=False)
        if not isinstance(gokudo, int) or gokudo <= 0:
            die(
                "個人連帯保証を使う場合は contract.guarantee.gokudogaku_yen(極度額)の"
                "記入が必須です。極度額の定めのない個人根保証契約は無効です(民法465条の2)。"
            )

    # ハザード情報: 未記入のまま書面を作らせない
    hazard = cfg.get("hazard") or {}
    for key in ("dosha_keikai", "shinsui"):
        if hazard.get(key) is None:
            die(
                f"hazard.{key} が未記入です。市町村ハザードマップで確認のうえ "
                "true/false を明記してください(借主に説明すべき事項です)。"
            )
    if hazard.get("shinsui") and not hazard.get("shinsui_depth"):
        die("浸水想定区域に該当する場合は hazard.shinsui_depth(想定浸水深)を記入してください")

    buildings = get(cfg, "property.buildings")
    if not any(b.get("leased") for b in buildings):
        die("property.buildings に leased: true の棟が1つもありません")

    hot_water = get(cfg, "utilities.hot_water")
    unit = get(cfg, "utilities.hot_water_unit", required=(hot_water != "なし"),
               default="なし")
    if unit not in HOT_WATER_UNIT:
        die(f"utilities.hot_water_unit は {HOT_WATER_UNIT} のいずれかにしてください")
    if unit == "残置物":
        names = " ".join(z.get("name", "") for z in cfg.get("zanchibutsu") or [])
        if "給湯" not in names and "湯沸" not in names:
            warn(
                "給湯器を残置物扱いにしていますが zanchibutsu に給湯器の記載がありません。"
                "物件状況報告書との整合のため追記を推奨します。"
            )
    if hot_water == "プロパン" and not get(cfg, "utilities.propane_contract_holder",
                                           required=False):
        warn("プロパンのボンベ契約名義 utilities.propane_contract_holder が未記入です")


def check_privacy(config_path: Path) -> None:
    """実物件データがgitにコミットされ得る状態ならビルドを止める。"""
    def ignored(p: Path) -> bool:
        r = subprocess.run(
            ["git", "check-ignore", "-q", str(p)],
            cwd=KIT_DIR, capture_output=True,
        )
        return r.returncode == 0

    def tracked(p: Path) -> bool:
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(p)],
            cwd=KIT_DIR, capture_output=True,
        )
        return r.returncode == 0

    in_git = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=KIT_DIR, capture_output=True,
    ).returncode == 0
    if not in_git:
        warn("gitリポジトリ外で実行されています。プライバシーチェックをスキップします。")
        return

    probe = OUTPUT_DIR / "_privacy_probe"
    OUTPUT_DIR.mkdir(exist_ok=True)
    probe.touch()
    try:
        if not ignored(probe):
            die(
                "output/ が .gitignore で除外されていません。生成書面には住所等が"
                "含まれるため、kashiya-kit/.gitignore に `output/` がある状態に"
                "戻してから再実行してください。"
            )
    finally:
        probe.unlink()

    if config_path.name != "property_sample.yaml":
        if tracked(config_path):
            die(
                f"{config_path.name} は既にgitで追跡されています。実物件のconfigは"
                "コミット禁止です。`git rm --cached` で追跡を外してください。"
            )
        if not ignored(config_path):
            die(
                f"{config_path.name} が .gitignore で除外されていません。"
                "追跡対象にしてよいのは架空データの property_sample.yaml のみです。"
            )


def build_context(cfg: dict, config_stem: str) -> dict:
    buildings = get(cfg, "property.buildings")
    leased = [b for b in buildings if b.get("leased")]
    private = [b for b in buildings if not b.get("leased")]
    utilities = cfg.get("utilities") or {}
    drainage = utilities.get("drainage")
    hot_water = utilities.get("hot_water")
    unit = utilities.get("hot_water_unit") or "なし"
    pet = cfg.get("pet") or {}

    return {
        "p": cfg["property"],
        "hazard": cfg.get("hazard") or {},
        "c": cfg["contract"],
        "u": utilities,
        "zanchibutsu": cfg.get("zanchibutsu") or [],
        "defects": cfg.get("defects") or [],
        "pet": pet,
        "diy": cfg.get("diy") or {},
        "manga": cfg.get("manga") or {},
        # 導出フラグ
        "teiki": get(cfg, "contract.type") == "定期借家",
        "leased_buildings": leased,
        "private_buildings": private,
        "leased_names": "・".join(b["name"] for b in leased),
        "private_names": "・".join(b["name"] for b in private),
        "johkaso": drainage == "浄化槽",
        "kumitori": drainage == "汲取り",
        "ido": utilities.get("water") == "井戸",
        "propane": hot_water == "プロパン",
        "kyutoki_setsubi": unit == "設備",
        "kyutoki_zanchi": unit == "残置物",
        "has_niwa_hatake": bool(cfg["property"].get("garden") or cfg["property"].get("farm")),
        "pet_ok": bool(pet.get("allowed")),
        "g_type": get(cfg, "contract.guarantee.type"),
        "gen_date": date.today().strftime("%Y年%m月%d日"),
        "config_stem": config_stem,
    }


HTML_SHELL = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head><body>
{body}
</body></html>
"""


def main() -> None:
    if len(sys.argv) < 2:
        die("使い方: python3 build.py config/property_XXX.yaml")
    config_path = Path(sys.argv[1]).resolve()
    if not config_path.exists():
        die(f"{config_path} が見つかりません")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate(cfg)
    check_privacy(config_path)

    stem = config_path.stem
    ctx = build_context(cfg, stem)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["yen"] = lambda n: f"{n:,}円" if isinstance(n, int) else (n or "―")

    out_md = OUTPUT_DIR / stem / "md"
    out_html = OUTPUT_DIR / stem / "html"
    out_md.mkdir(parents=True, exist_ok=True)
    out_html.mkdir(parents=True, exist_ok=True)

    css = (TEMPLATE_DIR / "print.css").read_text(encoding="utf-8")
    templates = sorted(t for t in env.list_templates() if t.endswith(".md.j2"))

    for name in templates:
        # 定期借家の事前説明書面は定期借家のときだけ出力する
        if "定期借家事前説明" in name and not ctx["teiki"]:
            continue
        text = env.get_template(name).render(**ctx)
        # 空行の連続を整理(条項の条件分岐で生じる)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        md_name = name[:-len(".md.j2")] + ".md"
        (out_md / md_name).write_text(text, encoding="utf-8")

        body = markdown.markdown(text, extensions=["tables", "sane_lists"])
        title = next(
            (ln.lstrip("# ").strip() for ln in text.splitlines()
             if ln.startswith("# ")),
            md_name,
        )
        html_name = md_name[:-3] + ".html"
        (out_html / html_name).write_text(
            HTML_SHELL.format(title=title, css=css, body=body), encoding="utf-8"
        )
        print(f"生成: {out_md / md_name}")

    print(f"\n完了: {len(list(out_md.glob('*.md')))}書面を {OUTPUT_DIR / stem} に生成しました。")
    print("HTMLをブラウザで開き、A4で印刷してください(背景印刷は不要)。")


if __name__ == "__main__":
    main()
