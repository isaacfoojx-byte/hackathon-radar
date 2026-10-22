import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from hackathon_radar.models import Event
from hackathon_radar.sources import devpost, email_source, luma, mlh, watchlist

log = logging.getLogger(__name__)

SOURCE_MODULES = {
    "devpost": devpost,
    "mlh": mlh,
    "luma": luma,
    "watchlist": watchlist,
    "email": email_source,
}


@contextmanager
def preserve_source_state():
    """Run previews against scratch copies, leaving real source state untouched.

    Stateful source modules declare ``STATE_PATH``. Discovering those paths
    from the source registry keeps dry-run handling automatic for future
    sources that follow the same convention.
    """
    originals = {}
    with tempfile.TemporaryDirectory(prefix="radar-dry-run-") as tmp:
        try:
            for name, source in SOURCE_MODULES.items():
                state_path = getattr(source, "STATE_PATH", None)
                if state_path is None:
                    continue
                scratch = Path(tmp) / name / Path(state_path).name
                scratch.parent.mkdir()
                try:
                    shutil.copyfile(state_path, scratch)
                except FileNotFoundError:
                    pass
                originals[source] = state_path
                source.STATE_PATH = scratch
            yield
        finally:
            for source, state_path in originals.items():
                source.STATE_PATH = state_path


def fetch_all(config: dict) -> list[Event]:
    """Fetch from every enabled source; one source failing doesn't kill the run."""
    events: list[Event] = []
    for name, source in SOURCE_MODULES.items():
        source_cfg = config.get("sources", {}).get(name, {})
        if not source_cfg.get("enabled", True):
            continue
        try:
            fetched = source.fetch(source_cfg)
            log.info("%s: %d events", name, len(fetched))
            events.extend(fetched)
        except Exception:
            log.exception("%s: fetch failed, skipping", name)
    return events
