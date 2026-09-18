export type DiffMode = "word" | "char" | "line";
export type DiffFilter = "all" | "changes";
export interface DiffPart {
    value: string;
    added?: boolean;
    removed?: boolean;
}
export interface DiffStats {
    added: number;
    removed: number;
    unchanged: number;
    charsAdded: number;
    charsRemoved: number;
}
export declare function diffWords(oldText: string, newText: string): DiffPart[];
export declare function diffChars(oldText: string, newText: string): DiffPart[];
export declare function diffLines(oldText: string, newText: string): DiffPart[];
export declare function computeStats(parts: DiffPart[]): DiffStats;
export declare function filterParts(parts: DiffPart[], filter: DiffFilter): DiffPart[];
export declare function escapeHtml(text: string): string;
