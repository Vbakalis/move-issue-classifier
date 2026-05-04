import * as vscode from "vscode";
import { MoveDiagnostics } from "./diagnostics";

export class MoveFixActions implements vscode.CodeActionProvider {
    static readonly kinds = [vscode.CodeActionKind.QuickFix];

    constructor(private readonly diagnostics: MoveDiagnostics) {}

    provideCodeActions(
        document: vscode.TextDocument,
        _range: vscode.Range | vscode.Selection,
        context: vscode.CodeActionContext
    ): vscode.CodeAction[] {
        const ours = context.diagnostics.filter((d) => d.source === this.diagnostics.source);
        return ours.map((d) => {
            const rawCode = d.code;
            const label =
                typeof rawCode === "string" || typeof rawCode === "number"
                    ? String(rawCode)
                    : "Issue";
            const action = new vscode.CodeAction(
                `Move Classifier: Fix ${label} with Claude`,
                vscode.CodeActionKind.QuickFix
            );
            action.diagnostics = [d];
            action.isPreferred = true;
            action.command = {
                command: "move-classifier.fixDiagnostic",
                title: "Fix with Claude",
                arguments: [
                    {
                        uri: document.uri.toString(),
                        range: d.range,
                        label,
                        confidence: this.diagnostics.getConfidence(document.uri, d.range),
                        code: document.getText(d.range),
                    },
                ],
            };
            return action;
        });
    }
}
