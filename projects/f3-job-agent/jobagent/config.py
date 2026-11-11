"""Configuration from the environment (and .env), so the same image runs on the laptop, in
docker compose and in ECS. Secrets (ANTHROPIC_API_KEY, AIRTABLE_TOKEN, GMAIL_ACCESS_TOKEN,
ADMIN_TOKEN) are read here and never printed or logged.

    JOB_AGENT_HOME       project folder (default: this repo's projects/f3-job-agent)
    STATE_PATH           SQLite file                      default <home>/state/state.db
    RESULTS_DIR          digests, drafts, reports, traces default <home>/results
    PREFS_PATH           preferences YAML                 default <home>/data/preferences.yaml
    WHATSAPP_DIR         folder of exports (.txt/.json)   default <home>/data/whatsapp
    WHATSAPP_GROUPS      comma-separated chat names       default the three groups
    AIRTABLE_BASE_ID, AIRTABLE_TABLE, AIRTABLE_VIEW, AIRTABLE_TOKEN   live API (all four needed)
    AIRTABLE_CSV         a CSV from a shared view (instead of the API)
    AIRTABLE_FIXTURE     a saved API response             default <home>/data/airtable/new_jobs.json
    EXTRACTOR            heuristic | llm | replay:<path>  default heuristic (free)
    LLM_MODEL            llmkit spec                      default anthropic:claude-haiku-5-5
    DELIVERY             file | console | whatsapp        default file
    DIGEST_CHAT          the only chat a digest may go to default משרות
    DRAFTS               file | gmail | none              default file
    STATE_S3_BUCKET, STATE_S3_OBJECT   keep the SQLite file in S3 between ECS runs
    INBOX_S3_PREFIX      pull exports from s3://<bucket>/<prefix> into the parent of WHATSAPP_DIR
    OUTBOX_S3_PREFIX     write each digest to s3://<bucket>/<prefix><slot>.txt
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

HOME_DEFAULT = Path(__file__).resolve().parent.parent
GROUPS_DEFAULT = ("Tech Referrals Senior 5+", "Tech Referrals Mid 3-4", "קהילת הייטק דרום")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    home: Path = HOME_DEFAULT
    state_path: Path = HOME_DEFAULT / "state" / "state.db"
    results_dir: Path = HOME_DEFAULT / "results"
    prefs_path: Path = HOME_DEFAULT / "data" / "preferences.yaml"
    whatsapp_dir: Path = HOME_DEFAULT / "data" / "whatsapp"
    whatsapp_groups: tuple[str, ...] = GROUPS_DEFAULT
    airtable_base: str = ""
    airtable_table: str = ""
    airtable_view: str = "New Jobs"
    airtable_token: str = field(default="", repr=False)
    airtable_csv: str = ""
    airtable_fixture: str = ""
    extractor: str = "heuristic"
    llm_model: str = "anthropic:claude-haiku-5-5"
    delivery: str = "file"
    digest_chat: str = "משרות"
    drafts: str = "file"
    s3_bucket: str = ""
    s3_key: str = "job-agent/state.db"
    inbox_prefix: str = ""
    outbox_prefix: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from llmkit import load_dotenv

            load_dotenv(str(Path(_env("JOB_AGENT_HOME", str(HOME_DEFAULT))).parents[1] / ".env"))
        except Exception:
            pass
        home = Path(_env("JOB_AGENT_HOME", str(HOME_DEFAULT)))
        # Docker/compose secrets arrive as files: ANTHROPIC_API_KEY_FILE=/run/secrets/... (lesson 27).
        for var in ("ANTHROPIC_API_KEY", "AIRTABLE_TOKEN", "GMAIL_ACCESS_TOKEN"):
            f = _env(var + "_FILE")
            if f and not _env(var) and Path(f).is_file():
                value = Path(f).read_text(encoding="utf-8").strip()
                if value:
                    os.environ[var] = value
        prefs_path = Path(_env("PREFS_PATH", str(home / "data" / "preferences.yaml")))
        default_prefs = home / "data" / "preferences.yaml"
        if not prefs_path.exists() and default_prefs.exists():  # first start with PREFS_PATH on a volume
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            prefs_path.write_text(default_prefs.read_text(encoding="utf-8"), encoding="utf-8")
        groups = tuple(g.strip() for g in _env("WHATSAPP_GROUPS").split(",") if g.strip()) or GROUPS_DEFAULT
        return cls(
            home=home,
            state_path=Path(_env("STATE_PATH", str(home / "state" / "state.db"))),
            results_dir=Path(_env("RESULTS_DIR", str(home / "results"))),
            prefs_path=prefs_path,
            whatsapp_dir=Path(_env("WHATSAPP_DIR", str(home / "data" / "whatsapp"))),
            whatsapp_groups=groups,
            airtable_base=_env("AIRTABLE_BASE_ID"), airtable_table=_env("AIRTABLE_TABLE"),
            airtable_view=_env("AIRTABLE_VIEW", "New Jobs"), airtable_token=_env("AIRTABLE_TOKEN"),
            airtable_csv=_env("AIRTABLE_CSV"),
            airtable_fixture=_env("AIRTABLE_FIXTURE", str(home / "data" / "airtable" / "new_jobs.json")),
            extractor=_env("EXTRACTOR", "heuristic"), llm_model=_env("LLM_MODEL", "anthropic:claude-haiku-5-5"),
            delivery=_env("DELIVERY", "file"), digest_chat=_env("DIGEST_CHAT", "משרות"), drafts=_env("DRAFTS", "file"),
            s3_bucket=_env("STATE_S3_BUCKET"), s3_key=_env("STATE_S3_OBJECT", "job-agent/state.db"),
            inbox_prefix=_env("INBOX_S3_PREFIX"), outbox_prefix=_env("OUTBOX_S3_PREFIX"),
        )

    # ------------------------------------------------------------ factories
    def sources(self) -> list:
        from .sources import AirtableAPISource, AirtableCSVSource, AirtableFixtureSource, WhatsAppExportSource

        out = [WhatsAppExportSource(self.whatsapp_dir, self.whatsapp_groups)]
        if self.airtable_base and self.airtable_table and self.airtable_token:
            out.append(AirtableAPISource(self.airtable_base, self.airtable_table, self.airtable_view, self.airtable_token))
        elif self.airtable_csv:
            out.append(AirtableCSVSource(self.airtable_csv, self.airtable_view))
        elif self.airtable_fixture:
            out.append(AirtableFixtureSource(self.airtable_fixture, self.airtable_view))
        return out

    def make_extractor(self, record: bool = False):
        from .extract import HeuristicExtractor, LLMExtractor, ReplayExtractor

        if self.extractor == "heuristic":
            return HeuristicExtractor()
        if self.extractor.startswith("replay:"):
            return ReplayExtractor(self.extractor.split(":", 1)[1])
        if self.extractor == "llm":
            from llmkit import LLM, RetryPolicy
            from obskit import InstrumentedLLM

            llm = InstrumentedLLM(LLM(self.llm_model, retry=RetryPolicy(max_attempts=3)), prompt_name="extract",
                                  prompt_version=__import__("jobagent.extract", fromlist=["x"]).PROMPT_VERSION)
            rec = self.home / "data" / "recorded" / f"{self.llm_model.split(':')[-1]}.jsonl" if record else None
            return LLMExtractor(llm, record=rec)
        raise ValueError(f"EXTRACTOR must be heuristic, llm or replay:<path>, got {self.extractor!r}")

    def make_delivery(self):
        from .delivery import ConsoleDelivery, FileDelivery, WhatsAppGroupDelivery

        if self.delivery == "console":
            return ConsoleDelivery()
        if self.delivery == "whatsapp":
            return WhatsAppGroupDelivery(self.digest_chat)  # needs a send_fn wired to your bridge
        return FileDelivery(self.results_dir / "digests")

    def make_drafts(self):
        from .delivery import FileDraftAdapter, GmailDraftAdapter

        if self.drafts == "none":
            return None
        if self.drafts == "gmail":
            return GmailDraftAdapter()
        return FileDraftAdapter(self.results_dir / "drafts")
