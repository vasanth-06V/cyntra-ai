"""Golden data for the coding-round reviewer: three starter problems with
reference solutions, and twelve labelled candidate solutions (six correct,
six wrong, in several languages).

Used three ways:
  * scripts/load_starter_questions.py loads PROBLEMS into the question bank;
  * scripts/judge_eval_live.py (owner-run) asks the real model to review every
    case and reports how often it agrees with the label;
  * tests/judge_eval/test_golden.py proves the labels are TRUE by executing
    the Python cases, so the live measurement is measuring the model, not our
    mislabelling.
"""

PROBLEMS = {
    "unique_substring": {
        "type": "coding",
        "topic": "strings",
        "difficulty": 2,
        "tags": ["strings", "sliding window", "hash map"],
        "question": (
            "Given a string s, return the length of the longest substring that contains no "
            "repeated characters. For example, \"abcabcbb\" -> 3 (\"abc\"), \"bbbbb\" -> 1, "
            "\"pwwkew\" -> 3 (\"wke\"). Aim for linear time."
        ),
        "solution_language": "Python",
        "solution_code": '''def length_of_longest_substring(s):
    last_seen = {}
    start = 0
    best = 0
    for i, ch in enumerate(s):
        if ch in last_seen and last_seen[ch] >= start:
            start = last_seen[ch] + 1
        last_seen[ch] = i
        best = max(best, i - start + 1)
    return best
''',
    },
    "merge_intervals": {
        "type": "coding",
        "topic": "arrays",
        "difficulty": 3,
        "tags": ["arrays", "sorting", "intervals"],
        "question": (
            "Given a list of intervals [start, end], merge all overlapping intervals and return "
            "the result sorted by start. Intervals that touch (e.g. [1,2] and [2,3]) count as "
            "overlapping. Example: [[1,3],[2,6],[8,10],[15,18]] -> [[1,6],[8,10],[15,18]]. "
            "The input may be unsorted."
        ),
        "solution_language": "Python",
        "solution_code": '''def merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''',
    },
    "debounce": {
        "type": "webd",
        "topic": "javascript",
        "difficulty": 2,
        "tags": ["javascript", "closures", "timers"],
        "question": (
            "Implement debounce(fn, wait) in JavaScript. It returns a function that delays "
            "calling fn until `wait` milliseconds have passed since the last time the returned "
            "function was invoked. fn must receive the arguments of the LAST invocation. "
            "Calling the returned function again before the wait is over restarts the timer."
        ),
        "solution_language": "JavaScript",
        "solution_code": '''function debounce(fn, wait) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, wait);
  };
}
''',
    },
}

# expected: "correct" -> the reviewer should answer correct / mostly_correct;
#           "wrong"   -> it should answer incorrect / incomplete.
# run: for Python cases, the function name and (args, expected) pairs used by
#      the label-truth test.
CASES = [
    # ---- unique substring
    {
        "id": "us_correct_set_window", "problem": "unique_substring", "language": "Python", "expected": "correct",
        "note": "different valid approach: set-based window",
        "code": '''def lengthOfLongestSubstring(s):
    seen = set()
    left = 0
    best = 0
    for right, ch in enumerate(s):
        while ch in seen:
            seen.remove(s[left])
            left += 1
        seen.add(ch)
        best = max(best, right - left + 1)
    return best
''',
        "run": ("lengthOfLongestSubstring", [(("abcabcbb",), 3), (("bbbbb",), 1), (("pwwkew",), 3), (("",), 0), (("abba",), 2)]),
    },
    {
        "id": "us_correct_js", "problem": "unique_substring", "language": "JavaScript", "expected": "correct",
        "note": "correct, different language",
        "code": '''function lengthOfLongestSubstring(s) {
  const last = new Map();
  let start = 0, best = 0;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (last.has(ch) && last.get(ch) >= start) start = last.get(ch) + 1;
    last.set(ch, i);
    best = Math.max(best, i - start + 1);
  }
  return best;
}
''',
    },
    {
        "id": "us_wrong_no_max", "problem": "unique_substring", "language": "Python", "expected": "wrong",
        "note": "subtle: jumps start backwards on 'abba' (missing the >= start check)",
        "code": '''def lengthOfLongestSubstring(s):
    last = {}
    start = 0
    best = 0
    for i, ch in enumerate(s):
        if ch in last:
            start = last[ch] + 1
        last[ch] = i
        best = max(best, i - start + 1)
    return best
''',
        "run": ("lengthOfLongestSubstring", [(("abcabcbb",), 3), (("bbbbb",), 1), (("pwwkew",), 3), (("",), 0), (("abba",), 2)]),
    },
    {
        "id": "us_wrong_distinct_count", "problem": "unique_substring", "language": "Python", "expected": "wrong",
        "note": "solves a different problem: counts distinct characters",
        "code": '''def lengthOfLongestSubstring(s):
    return len(set(s))
''',
        "run": ("lengthOfLongestSubstring", [(("abcabcbb",), 3), (("bbbbb",), 1), (("pwwkew",), 3), (("",), 0), (("abba",), 2)]),
    },
    # ---- merge intervals
    {
        "id": "mi_correct_reference_style", "problem": "merge_intervals", "language": "Python", "expected": "correct",
        "note": "correct, sorts with a key and builds with a stack",
        "code": '''def merge(intervals):
    intervals.sort(key=lambda p: p[0])
    out = [intervals[0][:]] if intervals else []
    for s, e in intervals[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
''',
        "run": ("merge", [(([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]), (([[1, 2], [2, 3]],), [[1, 3]]), (([],), []), (([[5, 6], [1, 2]],), [[1, 2], [5, 6]]), (([[1, 10], [2, 3]],), [[1, 10]])]),
    },
    {
        "id": "mi_correct_cpp", "problem": "merge_intervals", "language": "C++", "expected": "correct",
        "note": "correct, different language",
        "code": '''vector<vector<int>> merge(vector<vector<int>>& intervals) {
    sort(intervals.begin(), intervals.end());
    vector<vector<int>> out;
    for (auto& cur : intervals) {
        if (!out.empty() && cur[0] <= out.back()[1]) {
            out.back()[1] = max(out.back()[1], cur[1]);
        } else {
            out.push_back(cur);
        }
    }
    return out;
}
''',
    },
    {
        "id": "mi_wrong_unsorted", "problem": "merge_intervals", "language": "Python", "expected": "wrong",
        "note": "forgets to sort the (possibly unsorted) input",
        "code": '''def merge(intervals):
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''',
        "run": ("merge", [(([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]), (([[5, 6], [1, 2]],), [[1, 2], [5, 6]]), (([[1, 4], [0, 4]],), [[0, 4]])]),
    },
    {
        "id": "mi_wrong_touching", "problem": "merge_intervals", "language": "Python", "expected": "wrong",
        "note": "subtle: strict < so touching intervals are not merged, against the statement",
        "code": '''def merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
''',
        "run": ("merge", [(([[1, 2], [2, 3]],), [[1, 3]]), (([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]])]),
    },
    # ---- debounce
    {
        "id": "db_correct_arrow_state", "problem": "debounce", "language": "JavaScript", "expected": "correct",
        "note": "correct variant: keeps the latest args and one timer",
        "code": '''const debounce = (fn, wait) => {
  let id;
  return (...args) => {
    if (id) clearTimeout(id);
    id = setTimeout(() => fn(...args), wait);
  };
};
''',
    },
    {
        "id": "db_correct_ts", "problem": "debounce", "language": "TypeScript", "expected": "correct",
        "note": "correct, typed",
        "code": '''function debounce<T extends unknown[]>(fn: (...a: T) => void, wait: number) {
  let t: ReturnType<typeof setTimeout> | undefined;
  return (...args: T) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}
''',
    },
    {
        "id": "db_wrong_no_clear", "problem": "debounce", "language": "JavaScript", "expected": "wrong",
        "note": "never clears the previous timer: every call fires later (a delay, not a debounce)",
        "code": '''function debounce(fn, wait) {
  return function (...args) {
    setTimeout(() => fn(...args), wait);
  };
}
''',
    },
    {
        "id": "db_wrong_immediate", "problem": "debounce", "language": "JavaScript", "expected": "wrong",
        "note": "ignores wait: calls fn immediately and only records the time",
        "code": '''function debounce(fn, wait) {
  let last = 0;
  return function (...args) {
    last = Date.now();
    return fn(...args);
  };
}
''',
    },
]
