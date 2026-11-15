import re
import statistics
import unicodedata

def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def center(word):
    return (word['bbox']['y0'] + word['bbox']['y1']) / 2


def reading_lines(words, tolerance):
    """Cluster by vertical centers, then read left-to-right within each line."""
    lines = []
    for word in sorted(words, key=center):
        if not lines or abs(center(word) - statistics.median(center(w) for w in lines[-1])) > tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [' '.join(w['text'] for w in sorted(line, key=lambda w: w['bbox']['x0']))
            for line in lines]


