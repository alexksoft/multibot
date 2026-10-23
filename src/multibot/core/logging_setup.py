import logging
import re
import os


_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(\btoken[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(\bapi[_-]?key[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"\+?\d[\d\s\-]{8,}\d"),  # phone numbers
]


class SecretMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        masked_msg = _mask(str(record.msg))
        if masked_msg != str(record.msg):
            record.msg = masked_msg
        if record.args:
            if isinstance(record.args, dict):
                masked = {k: _mask(str(v)) if _needs_mask(str(v)) else v
                          for k, v in record.args.items()}
                if masked != record.args:
                    record.args = masked
            else:
                args = record.args if isinstance(record.args, tuple) else (record.args,)
                masked = tuple(_mask(str(a)) if isinstance(a, str) and _needs_mask(a) else a for a in args)
                if masked != args:
                    record.args = masked
        return True


def _needs_mask(text: str) -> bool:
    return any(pat.search(text) for pat in _SECRET_PATTERNS)


def _mask(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0)[:4] + "***", text)
    return text


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SecretMaskingFilter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[handler],
    )
