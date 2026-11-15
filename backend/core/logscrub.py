"""A logging filter that masks secrets. Log lines are for finding faults, not for keeping passwords, tokens or pay figures."""
import logging
import re

PATTERN = re.compile(r"(?i)(password|passwd|secret|token|authorization|salary)(['\"]?\s*[:=]\s*['\"]?)([^\s,'\"&}]+)")
BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")


def scrub(text):
    return PATTERN.sub(r"\1\2***", BEARER.sub(r"\1***", text))


class ScrubFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = scrub(record.getMessage())
            record.args = ()
        except Exception:  # a broken message must never stop logging
            pass
        return True
