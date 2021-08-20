import re
from difflib import SequenceMatcher

_lower_bound = 0.75

def _ratio(one, two):
    pair = SequenceMatcher(None, one, two)
    return int(round(100 * pair.ratio())) > _lower_bound

def _quick_ratio(one, two):
    pair = SequenceMatcher(None, one, two)
    return int(round(100 * pair.quick_ratio())) > _lower_bound

def _partial_ratio(one, two):
    sh, lo = (one, two) if len(one) <= len(two) else (two, one)
    pair = SequenceMatcher(None, sh, lo)

    blocks = pair.get_matching_blocks()

    scores = []
    for i, j, _ in blocks:
        start = max(j-i, 0)
        end = start + len(sh)
        sm = SequenceMatcher(None, sh, lo[start:end])
        ratio = sm.ratio()
        scores.append(ratio)

    return int(round(100 * max(scores))) > _lower_bound

_word_regex = re.compile(r'\W', re.IGNORECASE)

def _sort_tokens(phrase):
    phrase = _word_regex.sub(' ', phrase).lower().strip()
    return ' '.join(sorted(phrase.split()))

def _token_sort_ratio(one, two):
    one, two = _sort_tokens(one), _sort_tokens(two)
    return _ratio(one, two) > _lower_bound

def _quick_token_sort_ratio(one, two):
    one, two = _sort_tokens(one), _sort_tokens(two)
    return _quick_ratio(one, two) > _lower_bound

def _partial_token_sort_ratio(one, two):
    sh, lo = _sort_tokens(one), _sort_tokens(two)
    return _partial_ratio(sh, lo) > _lower_bound

def _fuzzy_test(one, two):
    return (_ratio(one, two) or _quick_ratio(one, two) or _partial_ratio(one, two)
            or _token_sort_ratio(one, two) or _quick_token_sort_ratio(one, two) or _partial_token_sort_ratio(one, two))

def _collect(text, data, store):
    for item in data:
        for element in item[0]:
            if text == element:
                return [True, item]
            if _fuzzy_test(text, element):
                if len(store) < 10:
                    store.append(element)
    return False
    
def find(text, collection):
    found = []
    if not collection:
        return [False, found]
    
    for key, value in collection.items():
        new = _collect(text, value, found)
        if new:
            new.append(key)
            return new
    return [False, found]
