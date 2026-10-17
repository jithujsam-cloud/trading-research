"""Labels that say how much to trust a number.

Every figure the reports print carries one of these, so a reader can tell a
broker record from a reconstruction, a modelled cost, or a what-if.
"""

from enum import Enum


class Label(str, Enum):
    VERIFIED = "verified"          # copied from a broker record without arithmetic
    DERIVED = "derived"            # computed only from verified records (e.g. FIFO round trips)
    ESTIMATED = "estimated"        # depends on a model or assumption (e.g. charge schedule)
    HYPOTHETICAL = "hypothetical"  # a what-if that did not happen; never evidence of an edge
    UNAVAILABLE = "unavailable"    # the data needed is missing

    def __str__(self) -> str:
        return self.value
