"""A document described once, in plain data. The PDF and the Word renderers both read this, so the two always say the same thing.

    Doc(kind="quotation", title=("Quotation", "عرض سعر"), number="QT/2026/3/0001", watermark=True,
        meta=[(label("client"), "Acme")], blocks=[Table(...), Para("..."), Signatures([...])])

Labels are (English, Arabic) pairs. Text the user typed is printed as it is: Arabic, English or a mix.
"""
from dataclasses import dataclass, field
from typing import Optional

Pair = tuple  # (english, arabic)


@dataclass
class Para:
    text: str
    bold: bool = False
    size: float = 10


@dataclass
class Heading:
    pair: Pair


@dataclass
class KeyValues:
    rows: list  # [(label pair, value string)]


@dataclass
class Table:
    headers: list  # [pair]
    rows: list  # [[str]]
    aligns: list  # "start" | "end" | "center" per column
    widths: list  # relative widths
    totals: list = field(default_factory=list)  # [(label pair, value string)] shown under the table, aligned to the end


@dataclass
class Signature:
    label: Pair
    name: str = ""
    when: str = ""
    image: Optional[bytes] = None  # PNG of a drawn signature
    stamp: Optional[bytes] = None  # PNG of the company stamp
    note: str = ""  # e.g. "Signed copy on file"


@dataclass
class Signatures:
    items: list


@dataclass
class Doc:
    kind: str
    title: Pair
    number: str = ""
    watermark: bool = False  # the DRAFT mark: printed on everything that is not final
    meta: list = field(default_factory=list)  # [(label pair, value string)] under the title
    blocks: list = field(default_factory=list)
    company: Pair = ("Innovation Accounting Solutions", "إنوفيشن لحلول المحاسبة")
    footer: str = ""
    filename: str = "document"


WATERMARK = ("DRAFT", "مسودة")
