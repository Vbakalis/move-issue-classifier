import * as vscode from "vscode";
import { ServerManager } from "./server";
import { classify, ClassifyResponse } from "./client";
import { askClaudeStream } from "./claude";
import { FixPanel } from "./panel";
import { MoveDiagnostics } from "./diagnostics";
import { MoveFixActions } from "./actions";
import { isLikelyMove, moveLikenessScore } from "./heuristic";

let serverManager: ServerManager | undefined;
let output: vscode.OutputChannel;
let diagnostics: MoveDiagnostics;
let statusBar: vscode.StatusBarItem;

// Classification cache: key = uri+content hash, value = result
const classifyCache = new Map<string, ClassifyResponse>();

function contentHash(text: string): string {
    let h = 0;
    for (let i = 0; i < text.length; i++) {
        h = ((h << 5) - h + text.charCodeAt(i)) | 0;
    }
    return h.toString(36);
}

function cacheKey(uri: vscode.Uri, code: string): string {
    return `${uri.toString()}::${contentHash(code)}`;
}

function setStatusBar(text: string, tooltip?: string) {
    statusBar.text = text;
    if (tooltip) statusBar.tooltip = tooltip;
    statusBar.show();
}

const MOVE_SELECTOR: vscode.DocumentSelector = [
    { language: "move" },
    { scheme: "file", pattern: "**/*.move" },
];

export async function activate(ctx: vscode.ExtensionContext) {
    output = vscode.window.createOutputChannel("Move Issue Classifier");
    ctx.subscriptions.push(output);

    // Status bar item
    statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
    statusBar.command = "move-classifier.diagnose";
    setStatusBar("$(check) NiceMove", "NiceMove — click to diagnose");
    ctx.subscriptions.push(statusBar);

    diagnostics = new MoveDiagnostics();
    ctx.subscriptions.push(diagnostics);

    ctx.subscriptions.push(
        vscode.languages.registerCodeActionsProvider(
            MOVE_SELECTOR,
            new MoveFixActions(diagnostics),
            { providedCodeActionKinds: MoveFixActions.kinds }
        )
    );

    // Clear diagnostics and cache when the file changes underneath them.
    ctx.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument((e) => {
            diagnostics.clear(e.document.uri);
            // Invalidate cache for changed file
            for (const k of classifyCache.keys()) {
                if (k.startsWith(e.document.uri.toString())) classifyCache.delete(k);
            }
        }),
        vscode.workspace.onDidCloseTextDocument((doc) => diagnostics.clear(doc.uri))
    );

    // Auto-classify on save (debounced; opt-in via setting).
    ctx.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument((doc) => {
            const cfg = vscode.workspace.getConfiguration("moveClassifier");
            if (!cfg.get<boolean>("classifyOnSave", false)) return;
            if (!isMoveDocument(doc)) return;
            scheduleAutoClassify(doc);
        })
    );

    serverManager = new ServerManager(ctx, output);
    if (vscode.workspace.getConfiguration("moveClassifier").get<boolean>("autoSpawnServer", true)) {
        serverManager.start().catch((err) => {
            output.appendLine(`Server start failed: ${err}`);
            vscode.window.showWarningMessage(
                `Move Classifier: local server failed to start (${err.message ?? err}). You can start it manually or disable auto-spawn in settings.`
            );
        });
    }

    ctx.subscriptions.push(
        vscode.commands.registerCommand("move-classifier.diagnose", () => runDiagnose(ctx)),
        vscode.commands.registerCommand(
            "move-classifier.fixDiagnostic",
            (payload: FixPayload) => runFixFromAction(ctx, payload)
        ),
        vscode.commands.registerCommand("move-classifier.restartServer", async () => {
            await serverManager?.stop();
            await serverManager?.start();
            vscode.window.showInformationMessage("Move Classifier: server restarted.");
        }),
        vscode.commands.registerCommand("move-classifier.scanWorkspace", () => runWorkspaceScan()),
        vscode.commands.registerCommand("move-classifier.applyFix", (args: ApplyFixArgs) => applyFixInline(args))
    );
}

export async function deactivate() {
    await serverManager?.stop();
}

interface FixPayload {
    uri: string;
    range: vscode.Range;
    label: string;
    confidence: number;
    code: string;
}

async function runDiagnose(ctx: vscode.ExtensionContext) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage("Move Classifier: no active editor.");
        return;
    }
    const sel = editor.selection;
    const usingSelection = !sel.isEmpty;
    const range = usingSelection
        ? new vscode.Range(sel.start, sel.end)
        : new vscode.Range(0, 0, editor.document.lineCount, 0);
    const code = editor.document.getText(usingSelection ? sel : undefined);
    if (!code.trim()) {
        vscode.window.showWarningMessage("Move Classifier: nothing to diagnose.");
        return;
    }

    const cfg = vscode.workspace.getConfiguration("moveClassifier");
    const serverUrl = cfg.get<string>("serverUrl") ?? "http://127.0.0.1:8765";
    const threshold = cfg.get<number>("confidenceThreshold") ?? 0.6;
    const apiKey = cfg.get<string>("anthropicApiKey") ?? "";
    const model = cfg.get<string>("claudeModel") ?? "claude-sonnet-4-5";

    // Check cache first
    const key = cacheKey(editor.document.uri, code);
    let result: ClassifyResponse;
    const cached = classifyCache.get(key);

    if (cached) {
        result = cached;
        output.appendLine(`[diagnose] cache hit`);
    } else {
        setStatusBar("$(loading~spin) NiceMove", "Classifying...");
        try {
            result = await vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: "Classifying Move snippet..." },
                () => classify(serverUrl, code)
            );
        } catch (err: any) {
            setStatusBar("$(error) NiceMove", "Classification failed");
            output.appendLine(`Classify failed: ${err}`);
            vscode.window.showErrorMessage(`Move Classifier: classify failed (${err.message ?? err}).`);
            return;
        }
        classifyCache.set(key, result);
    }

    const conf = (result.confidence * 100).toFixed(1);
    const headline = `${result.label}  (${conf}% confidence)`;
    output.appendLine(`[diagnose] ${headline}`);

    // Out-of-distribution guard: model is over-confident on non-Move input.
    const likeness = moveLikenessScore(code);
    if (!isLikelyMove(code)) {
        output.appendLine(`[diagnose] OOD guard: likeness=${likeness.toFixed(2)} — suppressing prediction.`);
        diagnostics.clear(editor.document.uri);
        setStatusBar("$(check) NiceMove", "OOD — not Move code");
        vscode.window.showInformationMessage(
            `Move Classifier: snippet does not look like Sui Move (likeness ${(likeness * 100).toFixed(0)}%) — skipping.`
        );
        return;
    }

    // Multi-label support: show top-2 predictions as separate diagnostics
    diagnostics.setMulti(editor.document.uri, range, result);

    if (result.label === "Perfect" && result.confidence >= threshold) {
        setStatusBar("$(check) NiceMove", `${headline} — no issues`);
        vscode.window.showInformationMessage(`Move Classifier: ${headline} — no issues detected.`);
        return;
    }

    setStatusBar("$(warning) NiceMove", headline);

    if (!apiKey) {
        const choice = await vscode.window.showWarningMessage(
            `Move Classifier: ${headline}. Configure your Anthropic API key in settings to get a fix suggestion from Claude.`,
            "Open Settings"
        );
        if (choice === "Open Settings") {
            vscode.commands.executeCommand("workbench.action.openSettings", "moveClassifier.anthropicApiKey");
        }
        return;
    }

    const labelForPrompt = result.confidence >= threshold ? result.label : "uncertain";
    await streamFix(ctx, {
        apiKey,
        model,
        code,
        label: result.label,
        labelForPrompt,
        confidence: result.confidence,
        uri: editor.document.uri.toString(),
        range: { start: { line: range.start.line, character: range.start.character }, end: { line: range.end.line, character: range.end.character } },
    });
}

async function runFixFromAction(ctx: vscode.ExtensionContext, payload: FixPayload) {
    const cfg = vscode.workspace.getConfiguration("moveClassifier");
    const apiKey = cfg.get<string>("anthropicApiKey") ?? "";
    const model = cfg.get<string>("claudeModel") ?? "claude-sonnet-4-5";
    const threshold = cfg.get<number>("confidenceThreshold") ?? 0.6;

    if (!apiKey) {
        const choice = await vscode.window.showWarningMessage(
            "Move Classifier: configure your Anthropic API key in settings to use Quick Fix.",
            "Open Settings"
        );
        if (choice === "Open Settings") {
            vscode.commands.executeCommand("workbench.action.openSettings", "moveClassifier.anthropicApiKey");
        }
        return;
    }

    const labelForPrompt = payload.confidence >= threshold ? payload.label : "uncertain";
    await streamFix(ctx, {
        apiKey,
        model,
        code: payload.code,
        label: payload.label,
        labelForPrompt,
        confidence: payload.confidence,
        uri: payload.uri,
        range: { start: { line: payload.range.start.line, character: payload.range.start.character }, end: { line: payload.range.end.line, character: payload.range.end.character } },
    });
}

function isMoveDocument(doc: vscode.TextDocument): boolean {
    return doc.languageId === "move" || doc.fileName.endsWith(".move");
}

const autoClassifyTimers = new Map<string, NodeJS.Timeout>();

function scheduleAutoClassify(doc: vscode.TextDocument) {
    const key = doc.uri.toString();
    const existing = autoClassifyTimers.get(key);
    if (existing) clearTimeout(existing);
    const t = setTimeout(() => {
        autoClassifyTimers.delete(key);
        autoClassify(doc).catch((err) => output.appendLine(`Auto-classify failed: ${err}`));
    }, 400);
    autoClassifyTimers.set(key, t);
}

async function autoClassify(doc: vscode.TextDocument) {
    const code = doc.getText();
    if (!code.trim() || !isLikelyMove(code)) {
        diagnostics.clear(doc.uri);
        return;
    }

    const cfg = vscode.workspace.getConfiguration("moveClassifier");
    const serverUrl = cfg.get<string>("serverUrl") ?? "http://127.0.0.1:8765";

    // Check cache first
    const key = cacheKey(doc.uri, code);
    let result: ClassifyResponse;
    const cached = classifyCache.get(key);
    if (cached) {
        result = cached;
    } else {
        try {
            result = await classify(serverUrl, code);
            classifyCache.set(key, result);
        } catch (err: any) {
            output.appendLine(`[auto-classify] failed for ${doc.uri.fsPath}: ${err.message ?? err}`);
            return;
        }
    }

    const range = new vscode.Range(0, 0, Math.max(0, doc.lineCount - 1), 0);
    diagnostics.setMulti(doc.uri, range, result);
    output.appendLine(
        `[auto-classify] ${doc.uri.fsPath} → ${result.label} (${(result.confidence * 100).toFixed(1)}%)`
    );
}

async function streamFix(
    ctx: vscode.ExtensionContext,
    args: {
        apiKey: string;
        model: string;
        code: string;
        label: string;
        labelForPrompt: string;
        confidence: number;
        uri?: string;
        range?: { start: { line: number; character: number }; end: { line: number; character: number } };
    }
) {
    const panel = FixPanel.open(ctx, {
        code: args.code,
        label: args.label,
        confidence: args.confidence,
        uri: args.uri,
        range: args.range,
    });

    try {
        await askClaudeStream(
            {
                apiKey: args.apiKey,
                model: args.model,
                code: args.code,
                label: args.labelForPrompt,
                confidence: args.confidence,
            },
            (chunk) => panel.appendChunk(chunk)
        );
        panel.done();
    } catch (err: any) {
        const msg = err?.message ?? String(err);
        output.appendLine(`Claude stream failed: ${msg}`);
        panel.fail(msg);
    }
}

// --- Workspace-wide scan ---

async function runWorkspaceScan() {
    const files = await vscode.workspace.findFiles("**/*.move", "**/build/**");
    if (files.length === 0) {
        vscode.window.showInformationMessage("NiceMove: no .move files found in workspace.");
        return;
    }

    const cfg = vscode.workspace.getConfiguration("moveClassifier");
    const serverUrl = cfg.get<string>("serverUrl") ?? "http://127.0.0.1:8765";

    setStatusBar("$(loading~spin) NiceMove", `Scanning ${files.length} files...`);

    let issues = 0;
    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "NiceMove: scanning workspace...", cancellable: true },
        async (progress, token) => {
            for (let i = 0; i < files.length; i++) {
                if (token.isCancellationRequested) break;
                const uri = files[i];
                progress.report({ message: `${i + 1}/${files.length}`, increment: 100 / files.length });

                const doc = await vscode.workspace.openTextDocument(uri);
                const code = doc.getText();
                if (!code.trim() || !isLikelyMove(code)) {
                    diagnostics.clear(uri);
                    continue;
                }

                const key = cacheKey(uri, code);
                let result: ClassifyResponse;
                const cached = classifyCache.get(key);
                if (cached) {
                    result = cached;
                } else {
                    try {
                        result = await classify(serverUrl, code);
                        classifyCache.set(key, result);
                    } catch (err: any) {
                        output.appendLine(`[scan] failed for ${uri.fsPath}: ${err.message ?? err}`);
                        continue;
                    }
                }

                const range = new vscode.Range(0, 0, Math.max(0, doc.lineCount - 1), 0);
                diagnostics.setMulti(uri, range, result);
                if (result.label !== "Perfect") issues++;
            }
        }
    );

    setStatusBar("$(check) NiceMove", `Scan complete: ${issues} issue(s) in ${files.length} files`);
    vscode.window.showInformationMessage(`NiceMove: scanned ${files.length} files, found ${issues} issue(s).`);
}

// --- Apply fix inline ---

interface ApplyFixArgs {
    uri: string;
    range: { start: { line: number; character: number }; end: { line: number; character: number } };
    newText: string;
}

async function applyFixInline(args: ApplyFixArgs) {
    const uri = vscode.Uri.parse(args.uri);
    const doc = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(doc);
    const range = new vscode.Range(
        args.range.start.line, args.range.start.character,
        args.range.end.line, args.range.end.character
    );
    await editor.edit((editBuilder) => {
        editBuilder.replace(range, args.newText);
    });
    // Clear cache for this file since content changed
    for (const k of classifyCache.keys()) {
        if (k.startsWith(uri.toString())) classifyCache.delete(k);
    }
    diagnostics.clear(uri);
    vscode.window.showInformationMessage("NiceMove: fix applied.");
}
