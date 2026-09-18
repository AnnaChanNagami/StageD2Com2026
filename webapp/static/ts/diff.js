// ============================================================
// diff.ts — Diff Scribe vs Correction (word / char / line)
// ============================================================
// --- tokenizers ----------------------------------------------
function tokenizeWords(text) {
    return text.match(/\S+\s*/g) ?? [];
}
function tokenizeChars(text) {
    return Array.from(text);
}
function tokenizeLines(text) {
    return text.split("\n").map((l) => l + "\n");
}
// --- LCS-based diff (O(n*m), léger, sans dépendance) ----------
function lcsDiff(oldTokens, newTokens) {
    const n = oldTokens.length;
    const m = newTokens.length;
    const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
        for (let j = m - 1; j >= 0; j--) {
            dp[i][j] = oldTokens[i] === newTokens[j]
                ? dp[i + 1][j + 1] + 1
                : Math.max(dp[i + 1][j], dp[i][j + 1]);
        }
    }
    const parts = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
        if (oldTokens[i] === newTokens[j]) {
            parts.push({ value: oldTokens[i] });
            i++;
            j++;
        }
        else if (dp[i + 1][j] >= dp[i][j + 1]) {
            parts.push({ value: oldTokens[i], removed: true });
            i++;
        }
        else {
            parts.push({ value: newTokens[j], added: true });
            j++;
        }
    }
    while (i < n)
        parts.push({ value: oldTokens[i++], removed: true });
    while (j < m)
        parts.push({ value: newTokens[j++], added: true });
    return parts;
}
// --- API publique --------------------------------------------
export function diffWords(oldText, newText) {
    return lcsDiff(tokenizeWords(oldText), tokenizeWords(newText));
}
export function diffChars(oldText, newText) {
    return lcsDiff(tokenizeChars(oldText), tokenizeChars(newText));
}
export function diffLines(oldText, newText) {
    return lcsDiff(tokenizeLines(oldText), tokenizeLines(newText));
}
export function computeStats(parts) {
    const s = { added: 0, removed: 0, unchanged: 0, charsAdded: 0, charsRemoved: 0 };
    for (const p of parts) {
        if (p.added) {
            s.added++;
            s.charsAdded += p.value.length;
        }
        else if (p.removed) {
            s.removed++;
            s.charsRemoved += p.value.length;
        }
        else
            s.unchanged++;
    }
    return s;
}
export function filterParts(parts, filter) {
    return filter === "changes" ? parts.filter((p) => p.added || p.removed) : parts;
}
export function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
}
