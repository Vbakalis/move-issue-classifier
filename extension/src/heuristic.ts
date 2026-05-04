/**
 * Cheap heuristic to decide whether a snippet "looks like Move" before
 * trusting the classifier's confidence. The model was trained on real
 * Sui Move and is over-confident on out-of-distribution input
 * (e.g. random English, Python, hand-typed pseudo-code).
 *
 * Returns a score in [0, 1]. Callers can compare against a threshold
 * to flag the input as out-of-distribution.
 */
export function moveLikenessScore(code: string): number {
    const trimmed = code.trim();
    if (trimmed.length < 10) return 0;

    const signals: Array<[RegExp, number]> = [
        [/\bmodule\s+\w+(::\w+)?\s*\{/, 0.35],
        [/\bpublic(\s+entry)?\s+fun\s+\w+/, 0.30],
        [/\bfun\s+\w+\s*[<(]/, 0.20],
        [/\bstruct\s+\w+\s+has\b/, 0.25],
        [/\b(use|friend)\s+\w+::/, 0.20],
        [/::\w+::\w+/, 0.15],
        [/&mut\s+\w+/, 0.10],
        [/\b(acquires|abort|move_to|move_from|borrow_global)\b/, 0.20],
        [/\b(TxContext|object|Coin|sui::)/, 0.15],
        [/\b(u8|u16|u32|u64|u128|u256|address|vector)\b/, 0.10],
    ];

    let score = 0;
    for (const [re, weight] of signals) {
        if (re.test(trimmed)) score += weight;
    }
    return Math.min(1, score);
}

export function isLikelyMove(code: string, threshold = 0.25): boolean {
    return moveLikenessScore(code) >= threshold;
}
