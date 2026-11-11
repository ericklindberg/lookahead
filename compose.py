"""Plain bounded output only: source strings are data, never instructions."""
import math
import unicodedata

from .contracts import aware


def sanitize(value, limit=160):
    value = ''.join(c for c in value if not unicodedata.category(c).startswith('C'))
    value = value.translate(str.maketrans('', '', '@<>[]()`*_\\'))
    return ' '.join(value.split())[:limit].strip().rstrip('.')


def compose(decision, now):
    if not decision.selected:
        return ''
    now = aware(now)
    lines = ['Lookahead:']
    for risk in decision.selected[:3]:
        if risk.help_offer:
            lines.append(f'- Ahead of {sanitize(risk.event.title)}: {sanitize(risk.detail)}.')
            lines.append('  Start with three points: what changed, one recovery option, and the decision or support you need.')
            continue
        minutes = max(1,math.ceil((risk.event.at-now).total_seconds()/60))
        unit = 'minute' if minutes == 1 else 'minutes'
        lines.append(f'- {sanitize(risk.event.title)} starts in {minutes} {unit}; {sanitize(risk.detail)}.')
    return '\n'.join(lines)
