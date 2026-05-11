import * as vscode from "vscode";
import { ClassifyResponse } from "./client";

/**
 * Owns a DiagnosticCollection for the Move Classifier and tracks
 * per-range confidence so CodeActions can pass it along.
 */
export class MoveDiagnostics implements vscode.Disposable {
    readonly source = "Move Classifier";
    private readonly col = vscode.languages.createDiagnosticCollection("move-classifier");
    private readonly confidences = new Map<string, number>();

    set(uri: vscode.Uri, range: vscode.Range, label: string, confidence: number): void {
        if (label === "Perfect") {
            this.clear(uri);
            return;
        }
        const conf = (confidence * 100).toFixed(1);
        const d = new vscode.Diagnostic(
            range,
            `${label} (${conf}% confidence). Use the Quick Fix lightbulb to ask Claude.`,
            severityFor(label)
        );
        d.source = this.source;
        d.code = label;
        this.col.set(uri, [d]);
        this.confidences.set(this.key(uri, range), confidence);
    }

    /** Multi-label: show primary + second prediction if confidence is meaningful */
    setMulti(uri: vscode.Uri, range: vscode.Range, result: ClassifyResponse): void {
        if (result.label === "Perfect") {
            this.clear(uri);
            return;
        }

        const diags: vscode.Diagnostic[] = [];
        const conf = (result.confidence * 100).toFixed(1);
        const primary = new vscode.Diagnostic(
            range,
            `${result.label} (${conf}% confidence). Use the Quick Fix lightbulb to ask Claude.`,
            severityFor(result.label)
        );
        primary.source = this.source;
        primary.code = result.label;
        diags.push(primary);
        this.confidences.set(this.key(uri, range), result.confidence);

        // Show second prediction as a hint if it's non-Perfect and confidence > 15%
        if (result.top_2 && result.top_2.length > 1) {
            const second = result.top_2[1];
            if (second.label !== "Perfect" && second.confidence > 0.15) {
                const conf2 = (second.confidence * 100).toFixed(1);
                const hint = new vscode.Diagnostic(
                    range,
                    `Also possible: ${second.label} (${conf2}% confidence)`,
                    vscode.DiagnosticSeverity.Hint
                );
                hint.source = this.source;
                hint.code = second.label;
                diags.push(hint);
            }
        }

        this.col.set(uri, diags);
    }

    getConfidence(uri: vscode.Uri, range: vscode.Range): number {
        return this.confidences.get(this.key(uri, range)) ?? 0;
    }

    clear(uri: vscode.Uri): void {
        this.col.set(uri, []);
        const prefix = uri.toString() + "::";
        for (const k of this.confidences.keys()) {
            if (k.startsWith(prefix)) this.confidences.delete(k);
        }
    }

    dispose(): void {
        this.col.dispose();
    }

    private key(uri: vscode.Uri, range: vscode.Range): string {
        return `${uri.toString()}::${range.start.line}:${range.start.character}-${range.end.line}:${range.end.character}`;
    }
}

function severityFor(label: string): vscode.DiagnosticSeverity {
    switch (label) {
        case "SecurityError":
            return vscode.DiagnosticSeverity.Error;
        case "SyntaxError":
        case "SemanticError":
            return vscode.DiagnosticSeverity.Error;
        case "StyleError":
            return vscode.DiagnosticSeverity.Warning;
        default:
            return vscode.DiagnosticSeverity.Information;
    }
}
