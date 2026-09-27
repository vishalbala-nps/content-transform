"""Every output format, in the order the UI lists them.

Adding a format is one new module in this package plus one line here.
"""

from app.formats import advisory, deck, exec_summary, linkedin, x_thread
from app.formats.base import OutputAdapter

ADAPTERS: dict[str, OutputAdapter] = {
    a.name: a
    for a in [
        linkedin.adapter,
        x_thread.adapter,
        exec_summary.adapter,
        deck.adapter,
        advisory.adapter,
    ]
}
