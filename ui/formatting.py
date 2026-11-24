"""Readable tables and exact money formatting without floating-point conversion."""

import textwrap
from datetime import timezone


def decimal_text(cents):
    """Return an exact decimal price suitable for editing or exporting."""
    return f"{cents // 100}.{cents % 100:02d}"


def money(cents):
    return f"PHP {cents // 100:,}.{cents % 100:02d}"


def decimal_amount(amount):
    whole, _, fraction = str(amount).partition(".")
    return f"{int(whole):,}.{fraction.ljust(2, '0')}"


def timestamp(value):
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M") + " local*"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def status(product):
    if product.quantity == 0:
        return "Out of stock"
    return "Low stock" if product.quantity <= product.reorder_level else "In stock"


def table(headers, rows, maximums, numeric=()):
    """Wrap long text rather than silently dropping part of a product or reason."""
    records = [[str(value) for value in row] for row in rows]
    if not records:
        return "No matching records."
    widths = [
        max(len(header), min(maximums[i], max(len(r[i]) for r in records)))
        for i, header in enumerate(headers)
    ]

    def render(row):
        return " | ".join(
            value.rjust(widths[i]) if i in numeric else value.ljust(widths[i])
            for i, value in enumerate(row)
        )

    lines = [render(headers), "-+-".join("-" * width for width in widths)]
    for record in records:
        wrapped = [
            textwrap.wrap(value, width=widths[i], replace_whitespace=False) or [""]
            for i, value in enumerate(record)
        ]
        for index in range(max(len(parts) for parts in wrapped)):
            lines.append(render([parts[index] if index < len(parts) else "" for parts in wrapped]))
    return "\n".join(lines)
