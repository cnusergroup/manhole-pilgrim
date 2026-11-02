"""Demo: Iceberg time travel on the cards table.

For each snapshot, count cards as of that snapshot -> shows how the collection grew series by series.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lakehouse import q  # noqa: E402

snaps = q('SELECT snapshot_id, committed_at FROM "cards$snapshots" ORDER BY committed_at', fetch=True)
print(f"{len(snaps)} snapshots")
for s in snaps[:3] + snaps[-2:]:
    r = q(f"SELECT count(*) AS n, max(series) AS s FROM cards FOR VERSION AS OF {s['snapshot_id']}", fetch=True)[0]
    print(s["committed_at"][:19], s["snapshot_id"], "cards:", r["n"], "max series:", r["s"])
